FROM mcr.microsoft.com/devcontainers/python:3.12

ARG DEBIAN_FRONTEND=noninteractive

ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=/usr/local/share/npm-global/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ripgrep \
    curl \
    bash \
    ca-certificates \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs

RUN mkdir -p /usr/local/share/npm-global /home/vscode/.claude \
    && chown -R vscode:vscode /home/vscode/.claude /usr/local/share/npm-global

RUN npm install -g @anthropic-ai/claude-code

USER vscode
ENV CLAUDE_CONFIG_DIR=/home/vscode/.claude

RUN CLAUDE_CONFIG_DIR=/home/vscode/.claude npx -y get-shit-done-cc@latest --claude --global

WORKDIR /workspaces

CMD ["/bin/bash"]