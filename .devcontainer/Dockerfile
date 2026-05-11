FROM mcr.microsoft.com/devcontainers/python:3.12

# Installa Node.js (necessario per Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Installa Claude Code globalmente
RUN npm install -g @anthropic-ai/claude-code