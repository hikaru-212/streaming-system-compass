# Contributing to Streaming System + Compass

Thank you for considering a contribution. This guide provides the shortest supported path from a clean clone to a reviewable change without requiring the full private or historical development context.

## Project Maturity and Scope

**Streaming System + Compass** is an active research and reference implementation. It explores:

* correctness in event-driven systems
* admission into accepted history
* semantic governance and runtime evidence
* authority boundaries for automated and AI-agent-facing systems

The repository is not presented as production-ready software, a production security product, or a packaged Python library.

Software contributions are made under the [Apache License 2.0](LICENSE). Documentation contributions follow the content-role boundary in the [Repository Licensing Map](LICENSE-CONTENT.md).

## Start Here

New contributors should begin with:

1. [Project README](README.md) — public purpose, architecture summary, current status, and quick start
2. [Documentation Guide](docs/README.md) — documentation categories and authority
3. [Compass Reading Path](docs/navigation/COMPASS_READING_PATH.md) — routes by topic and depth

You do not need to read every historical Stage document before making a small change. When terminology or responsibility boundaries evolved, current source and tests, accepted ADRs, and current boundary notes take precedence over older implementation plans and historical records.

## Environment

The currently verified baseline is:

```text
Python 3.12
PostgreSQL 16
```

The documented local PostgreSQL path uses Docker Compose and the PostgreSQL command-line client. See [Development Setup](docs/development/README.md) and [Local PostgreSQL Setup](docs/development/postgres_local_setup.md).

Use the repository-local virtual environment explicitly:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

Do not commit `.venv`, environment files, credentials, caches, or other local machine state.

## Test Workflows

### Quick Database-Independent Verification

For a change covered by the unit suite:

```bash
./.venv/bin/python -m pytest tests/unit -v
```

This path does not require a physical PostgreSQL database.

### Full PostgreSQL-Backed and CI-Equivalent Verification

The complete workflow requires:

* a full Git clone with complete repository history
* Python 3.12
* PostgreSQL 16
* Docker Compose for the documented local database path
* a PostgreSQL client providing `psql`
* a dedicated test database
* every migration applied in filename order
* `pytest-cov` and `flake8`

Install the current repository dependencies and developer verification tools:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes the repository dependencies from `requirements.txt` and declares the coverage and lint tools used by CI.

Start PostgreSQL and create the dedicated test database if it does not already exist:

```bash
docker compose up -d
docker exec -it streaming_compass_postgres \
  psql -U compass_user -d postgres \
  -c "CREATE DATABASE compass_test;"
```

Point the destructive test suite only at that database:

```bash
export TEST_DATABASE_URL="postgresql://compass_user:compass_password@localhost:5433/compass_test"
```

Apply every migration in order:

```bash
for migration in db/migrations/*.sql; do
  echo "Applying ${migration}..."
  psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration"
done
```

Run the same lint rule and coverage threshold used by CI:

```bash
./.venv/bin/flake8 . --extend-exclude=.venv \
  --count --select=E9,F63,F7,F82 --show-source --statistics
./.venv/bin/python -m pytest -v --durations=10 \
  --cov=src --cov-report=term-missing --cov-fail-under=80
```

## Full Git History Requirement

The complete test workflow includes Stage 4B.5 experiment verification that resolves a pinned historical commit and reads exact historical Git blobs. Complete Git history is therefore a test and experiment reproducibility input, not a generic application runtime dependency.

Use a normal full clone and do not use a shallow `--depth` checkout for the complete suite. This check should report `false`:

```bash
git rev-parse --is-shallow-repository
```

CI declares the same requirement through `fetch-depth: 0`.

## Test Database Safety

PostgreSQL integration fixtures may run destructive cleanup with `TRUNCATE ... RESTART IDENTITY CASCADE`.

The fixtures enforce two safeguards:

* `TEST_DATABASE_URL` must be present; destructive tests must not use `DATABASE_URL` directly.
* after connecting, the current database name must end with `_test` or the fixture fails closed.

Never point `TEST_DATABASE_URL` at a development, shared, staging, or production database. Use a disposable database dedicated to this repository's tests.

## Change Authority

Use the smallest authority check appropriate to the change:

* **Architecture or responsibility change:** inspect the current accepted ADRs and boundary notes for the affected responsibility before changing terminology or ownership.
* **Implementation change:** update the relevant executable tests and current implementation evidence when behavior changes.
* **Documentation-only correction:** preserve the distinction between current authority and historical records; do not rewrite history to make later terminology appear retroactive.

An ADR is not required for every small implementation or documentation change. Use one when a durable architecture decision genuinely needs to be recorded.

## Pull Requests

The existing [pull-request template](.github/pull_request_template.md) asks for purpose, scope, non-goals, design boundaries, validation, and related issues. Keep the response proportional to the change.

In particular:

* keep the change focused and explain its motivation and responsibility boundary;
* add or update tests when behavior changes;
* update current documentation when a public contract or behavior changes;
* do not silently rewrite historical implementation records or closeouts;
* do not include `.private` content, credentials, tokens, local environment files, caches, coverage output, or other generated machine state.

## Security Findings

Follow the [Security Policy](SECURITY.md). Do not publish exploitable security-sensitive details through an ordinary public issue.

## Licensing Contributions

Contributions are made under the repository license applicable to the contributed content's role, as described in [LICENSE-CONTENT.md](LICENSE-CONTENT.md): Apache-2.0 for software and executable content, and CC BY 4.0 for documentation, prose, and non-executable research evidence.

This repository currently requires neither a Contributor License Agreement nor a Developer Certificate of Origin sign-off.
