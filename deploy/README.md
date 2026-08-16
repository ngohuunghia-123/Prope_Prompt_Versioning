# Deploying Prope

ADR-0031: **CI publishes a tested image and the host pulls it.** The VM never
builds, never holds a compiler, and never sees a `.env` that came from GitHub.

Three moving parts:

| Where | What | Who places it |
|-------|------|---------------|
| `.github/workflows/ci.yml` | check → publish to GHCR → one SSH call | git |
| `deploy/docker-compose.prod.yml` | the seven services, images pinned by SHA | copied to the VM by hand |
| `deploy/deploy.sh` | the SSH **forced command** on the VM | copied to the VM by hand |

Everything below is the one-time manual setup. After it, a merge to `main`
deploys.

---

## 1. On the VM

Assumes Amazon Linux 2023 or Ubuntu 22.04+ with Docker and the compose plugin
installed.

### 1.1 A deploy account that cannot get a shell

```sh
sudo useradd --create-home --shell /bin/bash prope-deploy
sudo usermod -aG docker prope-deploy          # needed to run docker compose
sudo install -d -o prope-deploy -g prope-deploy -m 0750 /opt/prope /opt/prope/deploy
```

`docker` group membership is root-equivalent. That is exactly why the account's
key is restricted to a forced command below — the key can run one script, and the
script is in this repository where it can be reviewed.

### 1.2 The deployment bundle

Copy these from the repository to `/opt/prope` (scp, or `git clone` and copy out —
the VM does not need to keep a checkout):

```
/opt/prope/deploy/docker-compose.prod.yml
/opt/prope/deploy/deploy.sh              (chmod 0750, owned by prope-deploy)
/opt/prope/deploy/prometheus/            (whole directory)
/opt/prope/deploy/grafana/               (whole directory)
```

> **Re-copy `deploy/` whenever the Prometheus rules or the compose file change.**
> They are host state, not image content, so the pipeline does not carry them.
> This is the one drift risk in the setup; a rules change that never reaches the
> VM shows up as an alert that silently never fires.

### 1.3 `.env` — hand-placed, `0600`, never in CI (ADR-0032)

```sh
sudo -u prope-deploy touch /opt/prope/.env
sudo -u prope-deploy chmod 0600 /opt/prope/.env
```

Contents:

```dotenv
PROPE_IMAGE_PREFIX=ghcr.io/<owner>/<repo>     # all lowercase
PROPE_IMAGE_TAG=                              # deploy.sh rewrites this every deploy

POSTGRES_PASSWORD=...
PROPE_MIGRATE_PASSWORD=...
PROPE_APP_PASSWORD=...
PROPE_REPORT_PASSWORD=...
RABBITMQ_DEFAULT_USER=prope
RABBITMQ_DEFAULT_PASS=...
GRAFANA_ADMIN_PASSWORD=...

# ADR-0014 / A-135. 32 random bytes, base64. Encryption uses the HIGHEST version
# present; decryption uses the version the row names. This is the only copy —
# lose it and every stored provider credential is unrecoverable.
PROPE_KEK_V1=...

# A domain, if you have one pointed at this host: Caddy then provisions and
# renews the certificate itself over ACME (ports 80 and 443 must be reachable).
PROPE_SITE_ADDRESS=prope.example.com

# ONLY if you are reaching the host by bare IP over plain HTTP. A bare IP is not
# a domain, so there is no certificate, and a browser SILENTLY DISCARDS a
# `Secure` cookie over HTTP — sign-in answers 200 and every request after it is
# a 401 with nothing in any log. Delete this line the moment a domain exists.
# PROPE_COOKIE_SECURE=false
```

Generate secrets with `openssl rand -base64 32`.

### 1.4 Restrict the deploy key to the script

Generate the key pair **on your laptop**, not on the VM:

```sh
ssh-keygen -t ed25519 -f prope-deploy -N "" -C "github-actions"
```

Then on the VM, `/home/prope-deploy/.ssh/authorized_keys` (mode `0600`):

```
command="/opt/prope/deploy/deploy.sh",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-ed25519 AAAA...  github-actions
```

The `command=` prefix is the security property: sshd runs `deploy.sh` no matter
what the client asks for, and hands the client's string to the script in
`SSH_ORIGINAL_COMMAND`, where it is validated as a 40-character commit SHA before
being used. A leaked repository secret can ask for a different SHA. It cannot ask
for a shell.

### 1.5 A pull credential for GHCR

If the repository is private, the VM needs to authenticate to pull:

```sh
sudo -u prope-deploy docker login ghcr.io -u <github-user> --password-stdin
# paste a classic PAT with read:packages only
```

Public packages need nothing.

### 1.6 Security group

Inbound `80` and `443` from anywhere (ACME needs 80 even when you only serve
443), `22` from as narrow a range as you can manage. **Not** `9090` or `3000` —
`docker-compose.prod.yml` binds Prometheus and Grafana to `127.0.0.1`; reach them
with `ssh -L 9090:127.0.0.1:9090 prope-deploy@<host>`.

### 1.7 If a CDN or WAF sits in front of the domain

Not required, and nothing in this repository configures it — but if there is one,
**`/v1/*` must be exempted from bot protection or the gateway does not work.**

`/api` and the SPA are reached by browsers. `/v1` is reached by an SDK: no cookie,
no referer, no JavaScript, and a user-agent like `python-httpx`. That is the exact
signature bot protection exists to refuse, so the filter blocks a legitimate
consumer and answers with an HTML page where an OpenAI-compatible client expects
JSON. The client reports a parse error naming nothing, and the block is invisible
in Prope's own logs because the request never arrived.

Identify the service that fired before writing any rule — on Cloudflare, paste
the ray ID from the block page into Security → Events; the entry names whether it
was Bot Fight Mode, a managed rule, or a custom one, and they take different
levers. Then scope the exemption to the path:

```
(starts_with(http.request.uri.path, "/v1/"))   → Skip
```

Scope it to the path and nothing else. `/api` must keep whatever protection the
zone has: it is the browser surface, it holds the session cookie, and it is where
sign-in lives.

**Do not exempt `/v1` from rate limiting.** Prope's only volumetric control on the
gateway is a per-key *in-flight concurrency* cap (`gateway/routes.py`, refusal
reason `in_flight_cap`) — it bounds simultaneous requests, not the rate, and there
is no per-key quota or spend cap anywhere. So a CDN rate-limit rule on `/v1` is
not redundant with anything; it is the only thing of its kind. Every admitted call
spends the workspace's provider credit.

**This rule lives in a console and cannot be asserted from here.** It is written
down in this repository because that is the only place it can be reviewed — if the
gateway starts refusing consumers after a zone change, this is the first thing to
check.

---

## 2. In GitHub

**Settings → Environments → New environment → `production`.** Add a required
reviewer there if you want a human gate before each deploy; the workflow already
targets this environment, so nothing in the file changes.

**Environment secrets** (Settings → Environments → production → Secrets):

| Secret | Value |
|--------|-------|
| `DEPLOY_HOST` | the VM's public DNS name or IP |
| `DEPLOY_USER` | `prope-deploy` |
| `DEPLOY_SSH_KEY` | the **private** key from §1.4, whole file including header and footer |
| `DEPLOY_KNOWN_HOSTS` | output of `ssh-keyscan -t ed25519 <host>` — run it from a network you trust |

No registry secret: `publish` uses the built-in `GITHUB_TOKEN` with
`packages: write`.

**Settings → Actions → General → Workflow permissions** must allow
`GITHUB_TOKEN` to write packages (either "Read and write permissions", or leave
it read-only — the job's own `permissions: packages: write` block covers it).

---

## 3. The first deploy

The `deploy` job needs the account and the bundle to exist already, so run one by
hand first to prove the path:

```sh
sudo -u prope-deploy SSH_ORIGINAL_COMMAND=<a sha already in GHCR> /opt/prope/deploy/deploy.sh
```

Then merge to `main` and watch the Actions tab. Afterwards, create the first user
through the SPA's sign-up page — `POST /api/v1/auth/register` creates the user,
their own workspace, and their Admin binding in one transaction.

## 4. Rolling back

Images are tagged by commit and kept in GHCR, so a rollback is a tag change:

```sh
cd /opt/prope
sudo -u prope-deploy sed -i 's/^PROPE_IMAGE_TAG=.*/PROPE_IMAGE_TAG=<older sha>/' .env
sudo -u prope-deploy docker compose --env-file .env -f deploy/docker-compose.prod.yml up -d
```

**Migrations are the asymmetric half.** A rollback across a migration is a
forward migration, not a tag change. `deploy.sh` deliberately does not roll back
automatically for this reason — on a failed health check it restores
`PROPE_IMAGE_TAG` to the previous value and stops, leaving the decision to a
person.
