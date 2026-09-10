FROM node:22-bookworm-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} claude 2>/dev/null || true; \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash claude 2>/dev/null || true; \
    mkdir -p /workspace && chown -R ${UID}:${GID} /workspace

WORKDIR /workspace
USER claude

# Default command - keep container running for interactive use
ENTRYPOINT ["claude"]
CMD ["--dangerously-skip-permissions"]
