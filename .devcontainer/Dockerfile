# =============================================================================
# Dockerfile -- dbt Escape Room devcontainer
# =============================================================================
#
#   Base image:  ghcr.io/astral-sh/uv:python3.12-bookworm-slim
#                Python 3.12 + uv pre-installed. Slim Debian, nothing extra.
#
#   No venv:     The container IS the isolation.
#   No features: User creation and zsh are handled here to avoid the known TLS
#                issue where VS Code's Node.js fails to fetch features from
#                ghcr.io on some macOS machines.
#
# =============================================================================

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Create non-root user.
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/zsh ${USERNAME}

# git:              dbt deps for git-hosted packages + version control.
# zsh + curl + ca-certificates: comfortable shell + Oh My Zsh installer.
# just:             task runner used by the project's justfile.
# unzip:            needed to extract the DuckDB CLI zip.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        zsh \
        curl \
        ca-certificates \
        unzip \
        socat \
    && curl -LsSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# DuckDB CLI -- arch-aware so the image builds on both amd64 and arm64.
RUN ARCH=$(uname -m) \
    && case "$ARCH" in \
        x86_64)  DUCK_ARCH="amd64" ;; \
        aarch64) DUCK_ARCH="arm64" ;; \
        *) echo "Unsupported arch: $ARCH" && exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/duckdb/duckdb/releases/latest/download/duckdb_cli-linux-${DUCK_ARCH}.zip" -o /tmp/duckdb.zip \
    && unzip /tmp/duckdb.zip -d /usr/local/bin \
    && rm /tmp/duckdb.zip

# Oh My Zsh (optional comfort, ~20MB -- delete these two lines if unwanted).
USER ${USERNAME}
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

# Smoke test.
USER root
RUN uv --version && just --version && duckdb --version

USER ${USERNAME}
WORKDIR /workspaces
