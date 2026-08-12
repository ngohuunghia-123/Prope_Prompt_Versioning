#!/usr/bin/env bash
#
# ADR-0031's deploy step, as run ON THE VM. CI never runs this file; CI opens an
# SSH connection and this is what that connection is allowed to execute.
#
# **It is the forced command, and that is the security property.** The deploy
# account's `authorized_keys` entry pins `command="/opt/prope/deploy/deploy.sh"`, so
# a leaked repository secret can run this script and cannot run an arbitrary shell.
# The tag CI wants therefore does NOT arrive as an argument — OpenSSH discards the
# client's command line and puts it in `SSH_ORIGINAL_COMMAND`, which this script
# reads and then validates against a strict pattern. That validation is not
# decoration: `SSH_ORIGINAL_COMMAND` is attacker-controlled by construction, and it
# is interpolated into a `docker compose` invocation below.
#
# What it does, in ADR-0031's order:
#
#   1. pull the two images at the requested SHA — the host never builds
#   2. run migrations as their own step, as the superuser, and stop if they fail
#   3. recreate the services
#   4. wait for `app` to answer, and roll the tag back in `.env` if it does not
#
# Install it as:
#
#   sudo -u prope-deploy install -m 0750 deploy.sh /opt/prope/deploy/deploy.sh
#
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/prope}"
COMPOSE_FILE="${DEPLOY_ROOT}/deploy/docker-compose.prod.yml"
ENV_FILE="${DEPLOY_ROOT}/.env"

# 40 lowercase hex characters and nothing else. A tag is a commit SHA, so anything
# that is not one is either a mistake or an injection attempt, and both deserve the
# same answer. `latest` and `main` are deliberately NOT accepted: a moving tag makes
# "which artefact is running" unanswerable, and ADR-0031's rollback story is
# `PROPE_IMAGE_TAG=<older sha>`, which only works if tags are immutable.
readonly TAG_PATTERN='^[0-9a-f]{40}$'

log() { printf '[deploy] %s\n' "$*" >&2; }
die() { printf '[deploy] FATAL: %s\n' "$*" >&2; exit 1; }

requested="${SSH_ORIGINAL_COMMAND:-${1:-}}"
[[ -n "${requested}" ]] || die "no tag given; expected a 40-character commit SHA"
[[ "${requested}" =~ ${TAG_PATTERN} ]] || die "refusing tag '${requested}': not a commit SHA"

[[ -f "${COMPOSE_FILE}" ]] || die "no compose file at ${COMPOSE_FILE}"
[[ -f "${ENV_FILE}" ]] || die "no .env at ${ENV_FILE} — it is hand-placed (ADR-0032)"

cd "${DEPLOY_ROOT}"

# The tag currently deployed, so a failed health check has somewhere to go back to.
previous="$(grep -E '^PROPE_IMAGE_TAG=' "${ENV_FILE}" | tail -n1 | cut -d= -f2- || true)"
log "requested ${requested}; currently ${previous:-<none>}"

write_tag() {
	local tag="$1"
	# Rewrite in place via a temp file in the same directory, then `mv`, so a
	# process reading `.env` concurrently sees one version or the other and never a
	# truncated one. `.env` is 0600 and holds the KEK, so the temp file is created
	# with the same mode before anything is written into it.
	local tmp
	tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
	chmod 0600 "${tmp}"
	# `|| true` because grep exits 1 when it selects no lines, which under `set -e`
	# would abort the deploy on the one `.env` that contains nothing but the tag.
	grep -vE '^PROPE_IMAGE_TAG=' "${ENV_FILE}" > "${tmp}" || true
	printf 'PROPE_IMAGE_TAG=%s\n' "${tag}" >> "${tmp}"
	mv "${tmp}" "${ENV_FILE}"
}

compose() { docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"; }

write_tag "${requested}"

# 1. Pull first, and pull BEFORE stopping anything. A tag that does not exist in
#    GHCR — a deploy racing its own build, a retention policy that expired an old
#    SHA during a rollback — fails here, with everything still running.
log "pulling images at ${requested}"
compose pull app worker caddy

# 2. Migrations as their own step (ADR-0031), and `run --rm` rather than `up`:
#    `docker compose run` starts the service's dependencies, runs the one-shot in
#    the foreground, and EXITS WITH ITS EXIT CODE — which is the whole point of
#    making this a step. (`up --exit-code-from` would also tear down `postgres` when
#    the one-shot exits, which is the opposite of what a migration step wants.)
#
#    Step 3's `up -d` starts `migrate` a second time because `app` gates on it with
#    `service_completed_successfully`. That second pass is an `alembic upgrade head`
#    against a database already at head — a no-op — and it is left in place because
#    it is compose's own gate and not ours to weaken.
log "running migrations"
compose run --rm migrate || {
	log "migrations failed; rolling the tag back to ${previous:-<none>}"
	[[ -n "${previous}" ]] && write_tag "${previous}"
	die "migration step failed — nothing was recreated, the running release is untouched"
}

# 3. Recreate. `--remove-orphans` catches a service that was renamed or dropped
#    between releases; without it the old container keeps running and keeps holding
#    its port.
log "recreating services"
compose up -d --remove-orphans

# 4. Wait for the API. Compose's `depends_on: service_healthy` gates STARTUP order
#    and returns as soon as it is satisfied, so without this the deploy reports
#    success the moment the containers exist — which is before the new code has
#    proved it can answer.
log "waiting for app to become healthy"
for _ in $(seq 1 30); do
	container="$(compose ps -q app 2>/dev/null | head -n1 || true)"
	if [[ -n "${container}" ]]; then
		# Read the health state off the container rather than parsing `compose ps`
		# output: compose's `--format` accepts `table` and `json` and not an
		# arbitrary Go template, so a template there silently formats nothing and
		# this loop would time out on every deploy.
		state="$(docker inspect -f '{{.State.Health.Status}}' "${container}" 2>/dev/null || true)"
		[[ "${state}" == "healthy" ]] && { log "deployed ${requested}"; exit 0; }
	fi
	sleep 5
done

log "app did not become healthy within 150s"
compose logs --tail 100 app >&2
# The tag goes back so the NEXT `docker compose up -d` — by hand, at 3am, by whoever
# is holding the pager — starts the release that was working. Nothing is restarted
# automatically here: an automatic rollback across a migration that already applied
# is how a bad night becomes a bad week (ADR-0031, "migrations are the asymmetric
# half"). The decision is left to a person, and the tag is left correct for them.
if [[ -n "${previous}" ]]; then
	write_tag "${previous}"
	log "PROPE_IMAGE_TAG restored to ${previous}; run 'docker compose -f ${COMPOSE_FILE} up -d' to roll back"
fi
exit 1
