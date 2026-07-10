# Mac mini Development Migration

This guide moves Semantic Lighthouse development from Windows to macOS while
keeping source code in GitHub and runtime data outside Git.

## Migration Boundary

GitHub carries:

- application source, tests, migrations, scripts, and documentation
- the absorbed ontology article knowledge base in
  `docs/ontology-article-knowledge/`
- the current development branch:
  `codex/ontology-article-knowledge`

GitHub does not carry:

- `.env` or provider credentials
- SSH private keys
- PostgreSQL data or Docker volumes
- `.tmp/`, `dataset-storage/`, `document-storage/`, or `upload-tmp/`
- external source datasets that are not committed

Keep secrets out of migration archives. Use AirDrop, an encrypted drive, or
another private channel for non-Git runtime artifacts.

## 1. Install Mac Prerequisites

Install the Xcode command line tools:

```bash
xcode-select --install
```

Install Homebrew, then install the project Python version and GitHub CLI:

```bash
brew install python@3.14 gh
```

Install and start Docker Desktop for the Mac CPU architecture. Verify:

```bash
docker --version
docker compose version
docker info
```

## 2. Authenticate And Clone From GitHub

Use GitHub's browser login flow:

```bash
gh auth login --web --git-protocol https
gh auth status
```

Clone the repository and select the migration branch:

```bash
mkdir -p ~/Developer
cd ~/Developer
gh repo clone Chloride233/semantic-lighthouse
cd semantic-lighthouse
git switch codex/ontology-article-knowledge
git status -sb
git log -1 --oneline
```

Do not switch to `main` until the migration branch has been reviewed and
merged. Do not use force push during migration.

## 3. Create The Python Environment

Create a clean Mac virtual environment. Do not copy the Windows `.venv`:

```bash
"$(brew --prefix python@3.14)/bin/python3.14" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python --version
```

Create local configuration:

```bash
cp .env.example .env
openssl rand -hex 32
```

Put the generated value in `.env` as `JWT_SECRET_KEY`. Add provider keys only
on the Mac. Never commit `.env`.

Load `.env` into the current shell before running Alembic or the API:

```bash
set -a
source .env
set +a
```

## 4. Start The Local Application Database

The default development database is PostgreSQL 17 with pgvector:

```bash
POSTGRES_PASSWORD=semantic_lighthouse docker compose up -d postgres
docker compose ps
python -m alembic upgrade head
python -m alembic current
```

The password above matches the default local `DATABASE_URL` in `.env.example`.
Use a different password if the URL and Compose environment are changed
together.

Start the API:

```bash
python -m uvicorn semantic_lighthouse.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## 5. Restore The AdventureWorks Development State

The important Windows artifacts are the public benchmark source and semantic
pack:

- `.tmp/adventureworks`
- `.tmp/adventureworks-semantic`

After transferring the private archive to the Mac:

```bash
mkdir -p .tmp
unzip ~/Downloads/mac-migration-adventureworks-2026-07-10.zip -d .tmp
```

The runtime smoke output and test storage can be regenerated. They do not need
to be migrated.

The Tencent Cloud SQL Server stays on the cloud server. Create or register a
Mac SSH public key separately, then verify:

```bash
ssh ubuntu@SERVER_IP
```

Never commit the SSH private key. To export AdventureWorks again:

```bash
python scripts/export_adventureworks.py \
  --ssh-target ubuntu@SERVER_IP \
  --identity-file ~/.ssh/id_ed25519 \
  --output .tmp/adventureworks
```

## 6. Verify The Mac Workspace

Run focused migration checks first:

```bash
python scripts/check_doc_alignment.py
python -m pytest \
  tests/test_semantic_ci_pipeline.py \
  tests/test_adventureworks_export.py \
  tests/test_adventureworks_semantic_mapping.py \
  tests/test_adventureworks_ontology_seed.py \
  tests/test_db_runtime_query_smoke.py \
  -p no:cacheprovider
python -m ruff check src tests scripts
git diff --check
git status --short
```

Success means:

- the migration branch is tracking GitHub
- Python reports version 3.14 or newer
- PostgreSQL is healthy and Alembic reaches head
- focused semantic pipeline tests pass
- no secret or runtime artifact appears in `git status`
