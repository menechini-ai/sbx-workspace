# Base image shared by all agent containers
# Includes: system deps, npm setup, common tools, ai-memory CLI wrapper

FROM node:22-slim

ARG TZ=UTC
ARG USERNAME=node
ARG AI_MEMORY_VERSION=latest

ENV TZ=${TZ}
ENV DEVCONTAINER=true
ENV HOME=/home/${USERNAME}
ENV SHELL=/bin/zsh
ENV EDITOR=nano
ENV VISUAL=nano

# npm global packages directory
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=/usr/local/share/npm-global/bin:${PATH}

# ---------------------------------------------------------------------------
# System dependencies (shared)
# ---------------------------------------------------------------------------
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    dnsutils \
    fzf \
    gh \
    git \
    iproute2 \
    ipset \
    iptables \
    jq \
    less \
    man-db \
    nano \
    procps \
    sudo \
    unzip \
    vim \
    wget \
    zsh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# npm global directory permissions
RUN mkdir -p /usr/local/share/npm-global && \
    chown -R ${USERNAME}:${USERNAME} /usr/local/share/npm-global

# Persistent bash history
RUN mkdir -p /commandhistory && \
    touch /commandhistory/.bash_history && \
    chown -R ${USERNAME}:${USERNAME} /commandhistory

# Workspace directory
RUN mkdir -p /workspace && \
    chown -R ${USERNAME}:${USERNAME} /workspace

# ---------------------------------------------------------------------------
# Shared npm tools
# ---------------------------------------------------------------------------
RUN npm install -g \
        pyright \
        playwright && \
    npm cache clean --force

# ---------------------------------------------------------------------------
# git-delta
# ---------------------------------------------------------------------------
ARG GIT_DELTA_VERSION=0.18.2

RUN ARCH=$(dpkg --print-architecture) && \
    wget -q \
      "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" \
      -O /tmp/git-delta.deb && \
    dpkg -i /tmp/git-delta.deb && \
    rm -f /tmp/git-delta.deb

# ---------------------------------------------------------------------------
# ai-memory CLI wrapper
# ---------------------------------------------------------------------------
# Install the ai-memory wrapper script that runs the binary inside docker
# This allows the container to call `ai-memory run <agent>` for managed sessions
RUN mkdir -p /usr/local/bin && \
    curl -fsSL "https://github.com/akitaonrails/ai-memory/releases/latest/download/ai-memory-wrapper" \
      -o /usr/local/bin/ai-memory && \
    chmod +x /usr/local/bin/ai-memory

# Verify installation
RUN ai-memory --version

WORKDIR /workspace

USER ${USERNAME}

ENV HOME=/home/${USERNAME}
ENV PATH="/home/${USERNAME}/.local/bin:/usr/local/share/npm-global/bin:${PATH}"