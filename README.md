# dbt Escape Room

Hands-on dbt escape room challenges built on DuckDB and the jaffle shop dataset.

Each "room" is a small dbt task plus a SQL puzzle whose answer unlocks the next room. Challenges are launched via the Voyager terminal engine. The starting state is intentionally broken — the first room opens on a `stg_customers.sql` that won't compile.

## Requirements

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [just](https://just.systems/) — task runner
- [git](https://git-scm.com/)

## Quick Start

```bash
# 1. Install everything (Python deps, dbt packages, pre-commit hooks)
just setup

# 2. Verify setup (DuckDB needs no environment variables)
just verify

# 3. Load seed data
just seed

# 4. Launch Voyager and start the first room (TBD)
```

## Common Commands

```bash
just ui                           # launch Duckdb's UI
just run                          # run all models
just build                        # run + test all models in DAG order
just test                         # run all tests
just seed                         # load all seed CSVs
just snapshot                     # run snapshots
just full-refresh <model>         # full refresh a single model
just dbt <anything>               # generic passthrough (e.g. just dbt ls)
just source-freshness             # check source freshness
just lint                         # lint SQL
just fix                          # auto-fix SQL
just docs                         # generate + serve docs
just reset                        # wipe dev DB and restore from starter
just --list                       # see every recipe
```

## Project Structure

```
dbt_escape_room/
├── models/
│   ├── staging/            # Source cleaning, renaming, casting (views)
│   ├── intermediate/       # Business logic (ephemeral)
│   └── marts/              # Final output tables
├── snapshots/              # SCD Type 2 snapshots
├── macros/                 # Reusable Jinja macros
│   └── generate_schema_name.sql
├── tests/                  # Custom generic tests
├── seeds/                  # Static reference data (jaffle shop CSVs)
├── analyses/               # Ad-hoc SQL analyses
├── dbt_project.yml         # dbt project config
├── packages.yml            # dbt package dependencies
├── profiles.yml            # Warehouse connection config
├── .sqlfluff               # SQL linting rules
├── .pre-commit-config.yaml # Git pre-commit hooks
├── .gitignore
├── .env.example            # Environment variable reference
├── justfile                # Task runner commands
└── pyproject.toml          # Python dependencies (uv)
```

## Warehouse

This project uses **DuckDB** — a local file-based database. No environment variables or cloud credentials needed. Each target (`dev`, `acc`, `pro`) writes to its own `.duckdb` file in the project root.