set dotenv-load := true
set positional-arguments := true

# List all commands
default:
    @just --list

# -- Setup ---------------------------------
install:
    uv sync --all-groups

deps:
    uv run dbt deps

setup: install deps
    cp starter.duckdb dbt_escape_room_dev.duckdb
    @echo "Project ready!"

# -- dbt -----------------------------------
# Every dbt wrapper forwards extra args through to dbt, so any dbt flag works:
#   just run --select stg_customers
#   just build --select tag:marts --target pro
#   just test --select stg_customers
#   just full-refresh --select stg_payments_incremental
#   just seed --target acc
# Default target is `dev` (set in profiles.yml via DBT_TARGET env var).

compile *args:
    uv run dbt compile "$@"

run *args:
    uv run dbt run "$@"

build *args:
    uv run dbt build "$@"

test *args:
    uv run dbt test "$@"

seed *args:
    uv run dbt seed "$@"

snapshot *args:
    uv run dbt snapshot "$@"

debug *args:
    uv run dbt debug "$@"

# Generic dbt passthrough — use this for any dbt subcommand not wrapped above.
# Examples:
#   just dbt ls --quiet
#   just dbt ls --quiet --select +int_payment_totals_by_order
#   just dbt parse
#   just dbt run-operation drop_orphaned_objects
dbt *args:
    uv run dbt "$@"

# Check source freshness — surfaces stale sources defined with freshness configs.
# Example: just source-freshness --select source:jaffle_shop.raw_web_events
source-freshness *args:
    uv run dbt source freshness "$@"

full-refresh *args:
    uv run dbt run --full-refresh "$@"

docs *args:
    uv run dbt docs generate "$@"
    uv run dbt docs serve

# Propagate column descriptions from upstream to downstream YAML files.
# Run after updating descriptions in staging models to keep docs in sync.
osmosis *args:
    uv run dbt-osmosis yaml refactor "$@"

# -- Linting -------------------------------
lint:
    uv run sqlfluff lint models snapshots

fix:
    uv run sqlfluff fix models snapshots

lint-py:
    uv run ruff check .

format-py:
    uv run ruff format .

lint-all: lint lint-py

# -- Verify -------------------------------
verify *args:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Verifying project setup..."
    echo ""
    echo "OK: DuckDB requires no environment variables"
    echo ""
    echo "Checking dbt connection..."
    uv run dbt debug "$@" 2>&1 | tail -20
    echo ""
    echo "Compiling dbt project..."
    uv run dbt compile "$@"
    echo ""
    echo "All checks passed!"

# -- DuckDB --------------------------------
# Open the DuckDB UI at http://localhost:4213.
# socat bridges IPv4 (127.0.0.1) to IPv6 (::1) so VS Code's port-forwarding tunnel reaches DuckDB.
ui db="dbt_escape_room_dev.duckdb":
    #!/usr/bin/env bash
    set -euo pipefail
    socat TCP4-LISTEN:4213,bind=127.0.0.1,reuseaddr,fork TCP6:[::1]:4213 &
    SOCAT_PID=$!
    trap "kill $SOCAT_PID 2>/dev/null || true" EXIT
    duckdb -ui "{{db}}"

# Restore the dev database to its starter state (raw tables only, no models).
# Use this to reset between demos or after schema changes.
reset:
    rm -f dbt_escape_room_dev.duckdb
    cp starter.duckdb dbt_escape_room_dev.duckdb
    @echo "Done! Database reset to starter state."

# Regenerate starter.duckdb from scratch using Faker (maintainers only).
# After running, re-record puzzle answers in your maintainer playthrough notes.
generate-db:
    uv run --group scripts python scripts/generate_starter_db.py

# -- CI ------------------------------------
ci: deps lint-all build
