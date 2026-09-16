FROM node:22-bookworm-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gnupg \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Install pup CLI (Datadog) — official DataDog/pup repo
# Asset naming: pup_<version>_Linux_x86_64.tar.gz (pinned version, update as needed)
ARG PUP_VERSION=1.19.1
RUN curl -fsSL "https://github.com/DataDog/pup/releases/download/v${PUP_VERSION}/pup_${PUP_VERSION}_Linux_x86_64.tar.gz" \
    -o /tmp/pup.tar.gz && \
    tar -xzf /tmp/pup.tar.gz -C /tmp && \
    mv /tmp/pup /usr/local/bin/ && \
    rm /tmp/pup.tar.gz && \
    pup --version

# Install ai-memory CLI
RUN curl -fsSL https://github.com/akitaonrails/ai-memory/releases/download/v2.1.1/ai-memory-linux-x86_64.tar.gz \
    -o /tmp/ai-memory.tar.gz && \
    tar -xzf /tmp/ai-memory.tar.gz -C /tmp && \
    mv /tmp/ai-memory /usr/local/bin/ && \
    rm /tmp/ai-memory.tar.gz

# Install ai-memory hooks bundle
RUN curl -fsSL https://github.com/akitaonrails/ai-memory/releases/download/v2.1.1/ai-memory-hooks.tar.gz \
    -o /tmp/ai-memory-hooks.tar.gz && \
    mkdir -p /usr/local/share/ai-memory/hooks && \
    tar -xzf /tmp/ai-memory-hooks.tar.gz -C /usr/local/share/ai-memory/hooks --strip-components=1 && \
    rm /tmp/ai-memory-hooks.tar.gz

# Use existing 'node' user (UID 1000) from base image
# Pre-create claude temp directory to avoid permission issues
RUN mkdir -p /workspace /tmp/claude-1000 && chown -R node:node /workspace /tmp/claude-1000

WORKDIR /workspace
USER node

# Copy entrypoint script
COPY --chown=node:node entrypoint.sh /home/node/entrypoint.sh

# Default command - keep container running for interactive use
ENTRYPOINT ["/home/node/entrypoint.sh"]
CMD []
