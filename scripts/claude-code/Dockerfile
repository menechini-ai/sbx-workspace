# Claude Code image extending from base
# Adds: claude-code, browser-harness, claude plugins

FROM base:latest

ARG CLAUDE_CODE_VERSION=latest
ARG USERNAME=node

# Switch to root for installations
USER root

# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} && \
    npm cache clean --force

# ---------------------------------------------------------------------------
# Browser Harness (requires Python/uv)
# ---------------------------------------------------------------------------
# Install uv first
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /home/${USERNAME}/.local/bin/uv /usr/local/bin/uv && \
    chmod +x /usr/local/bin/uv

RUN uv tool install \
      --python 3.12 \
      --upgrade \
      --force \
      browser-harness \
    && mkdir -p /home/${USERNAME}/.claude/skills/browser-harness \
    && browser-harness skill \
        > /home/${USERNAME}/.claude/skills/browser-harness/SKILL.md \
    && browser-harness recordings disable \
    && browser-harness --doctor || true

# Ensure .claude directory is owned by node user before switching
RUN mkdir -p /home/${USERNAME}/.claude/plugins /home/${USERNAME}/.claude/skills && \
    chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.claude

# Fix home directory ownership (npm/uv create dirs as root)
RUN chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

# ---------------------------------------------------------------------------
# Switch to node user for claude plugin operations
# ---------------------------------------------------------------------------
USER ${USERNAME}

# ---------------------------------------------------------------------------
# Claude Code official plugins
# ---------------------------------------------------------------------------
RUN mkdir -p /home/${USERNAME}/.claude/plugins && \
    claude plugin marketplace add anthropics/claude-plugins-official || true && \
    claude plugin marketplace update claude-plugins-official && \
    claude plugin install superpowers@claude-plugins-official && \
    claude plugin install pyright-lsp@claude-plugins-official && \
    claude plugin install frontend-design@claude-plugins-official

# ---------------------------------------------------------------------------
# Shell / editor
# ---------------------------------------------------------------------------
ENV SHELL=/bin/zsh
ENV EDITOR=nano
ENV VISUAL=nano

# ---------------------------------------------------------------------------
# Default CLAUDE.md
# ---------------------------------------------------------------------------
RUN printf '%s\n' \
  '# Browser automation' \
  '' \
  'Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.' \
  > /home/${USERNAME}/.claude/CLAUDE.md

# ---------------------------------------------------------------------------
# Entrypoint - uses ai-memory managed run
# ---------------------------------------------------------------------------
COPY --chown=${USERNAME}:${USERNAME} entrypoint.sh /home/${USERNAME}/entrypoint.sh

RUN chmod +x /home/${USERNAME}/entrypoint.sh

ENTRYPOINT ["/home/node/entrypoint.sh"]