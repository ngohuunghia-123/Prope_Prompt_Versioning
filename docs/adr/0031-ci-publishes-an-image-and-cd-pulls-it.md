# ADR-0031 — CI publishes a tested image and CD pulls it over a restricted SSH channel

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global
**Related**: A-012, A-020, A-118, A-123, A-124, ADR-0025, ADR-0026, ADR-0027, ADR-0032, ADR-0033, BR-03

## Context

The repository already carries `.github/workflows/ci.yml`: checkout, `setup-python` at 3.11,
`pip install -r requirements.txt`, `ruff check src/ tests/`, `pytest`. `ruff.toml` exists and the
`Makefile` defines `lint`, `format`, `typecheck` (mypy) and `test`. The remote is GitHub. So the
pipeline *product* is settled by where the code lives; the decision is whether the pipeline also
deploys, and what it must verify before it does.

Step 3 wrote several promises that are only true if something checks them, and none of them is checked
by the inherited workflow:

- **ADR-0025** grants `prope_app` `INSERT` and `SELECT` on `history.history_event` and withholds
  `UPDATE` and `DELETE`. A grant that ships in a migration and is never tested is a grant someone
  removes during a bad night.
- **A-123** states property-history mounts no HTTP route at all, *"asserted by a route-table test rather
  than a rule, since the person who mounts `/api/v1/history` will be somebody reasonable who wants an
  audit screen."*
- **BR-03** is enforced by a database constraint, and **A-124**'s per-action key allow-list raises at
  append time. Both are database behaviours and neither can be verified against a mock.

## Decision

**GitHub Actions runs the full check suite against real service containers, builds one image, pushes it
to GHCR, and then deploys by SSH to the VM. The host pulls the published image; it never builds.**

- **Python 3.13** (ADR-0026), replacing the workflow's current 3.11.
- The test job runs with **PostgreSQL 17 and RabbitMQ 4 as service containers**, so contract, integration
  and the database-behaviour assertions above run against the real engines.
- Migrations are applied as `prope_migrate` and the suite then asserts, as `prope_app`, that the database
  itself refuses `UPDATE` and `DELETE` on `history.history_event` — the application guard is the thing
  being distrusted, so the assertion must come from the engine.
- The route table is asserted directly: no path is mounted for property-history, including `/healthz`
  and `/readyz`.
- `ruff` and `mypy` both gate. The `Makefile` targets stay the local equivalent so the pipeline is
  reproducible by hand.
- **One image** serves `app` and `worker` (ADR-0026, ADR-0028), tagged with the commit SHA and pushed to
  GHCR. A second, thin image carries Caddy with its configuration.
- **Deployment**: on a successful build of the default branch, a job connects over SSH and runs the
  deploy script, which pulls the tagged images, runs migrations as `prope_migrate` in a separate step,
  then restarts the services. Two properties make this defensible rather than merely fast:
  - the SSH key targets a **non-root deploy account** whose `authorized_keys` entry is restricted to a
    **forced command**, so a leaked repository secret can run the deploy script and not an arbitrary
    shell;
  - the host **pulls a published image and never builds**, so no compiler or build toolchain is
    installed beside the workspace credentials and stored request bodies.
- **`.env` never enters the pipeline** (ADR-0032). It is hand-placed on the VM once. The deploy script
  reads it via compose; CI neither writes nor reads it, so the KEK exists in exactly one place.

## Alternatives rejected

**Actions tests and publishes; a human deploys by running `make deploy` on the VM.** This was the
recommendation and it lost to the user's decision. Its case was that the VM is *group-controlled*, so
inbound SSH from GitHub's runners is a networking permission that may simply not be granted, and that a
pilot deploying a few times a week gains little from automation. It is the fallback if the network path
turns out to be unavailable, and it requires no change to anything else in this ADR, since the image is
published either way.

**A self-hosted GitHub runner on the VM.** Rejected on where it puts the execution surface. It solves
the inbound-SSH problem elegantly, and in exchange installs a build toolchain and a GitHub-triggered
execution environment on the same host as the workspace provider credentials and the stored request and
response bodies. That is a larger blast radius than a forced-command SSH account, for the same outcome.

**Deploying by building on the host (`git pull && docker compose up --build`).** Rejected because it
puts a compiler and the full dependency-resolution surface on the production box, makes deploys slow and
non-reproducible, and means the artefact that ran in CI is not the artefact that runs in production.

**Keeping CI as it is and deciding deployment later.** Rejected because the first deploy would then be
improvised by hand at the moment it most needs to be boring — and because the checks listed above are
needed regardless of how deployment happens.

## Consequences

- Four of step 3's promises stop being documentation and become build failures: ADR-0025's privilege,
  A-123's empty route table, BR-03's constraint, and A-124's allow-list.
- The deploy account, its forced command, and the GHCR pull credential are operational artefacts that
  have to exist before the first deploy. They are named here so they are provisioned deliberately rather
  than improvised.
- A rollback is `docker compose up -d` against the previous SHA tag, because images are tagged by commit
  and retained in GHCR. Migrations are the asymmetric half — a rollback across a migration is a forward
  migration, not a tag change.
- CI now needs PostgreSQL and RabbitMQ service containers, so the pipeline is slower than the inherited
  one. That is the cost of testing against engines rather than mocks, and it is the only way the
  database-level guarantees in ADR-0025, ADR-0027 and ADR-0035 can be verified at all.
- A-020 still governs what may run there: *"no real corporate prompts until the security baseline is
  signed off."* Automated deployment does not change what data the pilot is allowed to hold.

---

## Amendment, 2026-08-09 — the pipeline publishes two images, and gains a Node build stage

**ADR-0052 replaced the server-rendered UI with a React + TypeScript SPA built by Vite.** Nothing about
this ADR's shape changes — CI still builds and tests, GHCR still holds the artefacts, CD still pushes over
SSH to a forced-command non-root deploy account, and **the host still pulls and never builds**. What
changes is the count and one job step.

- **Two images, not one**: `prope-app` (unchanged — `app` and `worker` from the same image, different
  commands) and **`prope-web`**, a `FROM caddy:2` image with the Vite output copied into `/srv` and the
  `Caddyfile` alongside it. The deploy pulls two tags and recreates two services. `caddy` is therefore a
  built artefact rather than a stock image (ADR-0033, amended).
- **A Node build stage enters the image build, not the runtime.** `node:22-alpine` → `npm ci` →
  `npm run build`, then `COPY --from=build`. **No Node process runs in production**, which was the half of
  ADR-0034's argument ADR-0052 carried forward deliberately.
- **`npm audit` joins the job.** The dependency-vulnerability surface ADR-0034 declined arrives with the
  ecosystem that was asked for; it belongs in the same job as the Python checks, failing the build the
  same way.
- **The four step-3 promises this ADR turns into build failures are unaffected** — ADR-0025's privilege,
  A-123's empty route table, BR-03's constraint, A-124's allow-list. **A fifth and a sixth have since been
  added**: ADR-0045's tenant-coverage walk and, from release-control's pass, ADR-0008's `import-linter`
  layering contract. The frontend build sits beside them and gates the same pipeline.

**The versioning property is why the assets are baked in rather than mounted.** ADR-0052 rejected a
shared volume specifically so that `prope-web` and `prope-app` roll back together — otherwise a rollback
of the API leaves the previous deploy's SPA calling the current one, and *"the tested artefact is the
deployed one"* stops being true for the frontend. **The residual case is the browser, not the host**: a
tab already open across a deploy keeps running the old bundle. That is outside this pipeline's reach and
is recorded as **A-141**.
