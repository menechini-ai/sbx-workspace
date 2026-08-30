# OpenCode image extending from base
# Adds: opencode-ai

FROM base:latest

ARG OPENCODE_VERSION=latest
ARG USERNAME=node

# Switch to root for npm global install
USER root

# ---------------------------------------------------------------------------
# OpenCode
# ---------------------------------------------------------------------------
RUN npm install -g opencode-ai@${OPENCODE_VERSION} && \
    npm cache clean --force

# Fix home directory ownership (npm creates dirs as root)
RUN chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

# ---------------------------------------------------------------------------
# Switch back to node user
# ---------------------------------------------------------------------------
USER ${USERNAME}

# ---------------------------------------------------------------------------
# Entrypoint - uses ai-memory managed run
# ---------------------------------------------------------------------------
COPY --chown=${USERNAME}:${USERNAME} entrypoint.sh /home/${USERNAME}/entrypoint.sh

RUN chmod +x /home/${USERNAME}/entrypoint.sh

ENTRYPOINT ["/home/node/entrypoint.sh"]