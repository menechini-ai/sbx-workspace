FROM node:22-slim

RUN npm install -g opencode-ai

RUN apt-get update && apt-get install -y curl git ca-certificates && \
    curl https://mise.run | sh
ENV PATH="/root/.local/bin:/root/.local/share/mise/shims:${PATH}"
RUN mise use -g github:akitaonrails/ai-memory

WORKDIR /workspace
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]