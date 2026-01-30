FROM python:3.11.8-slim

LABEL maintainer="ZetoOfficial"
LABEL description="Automated SDLC Agent System with AI-powered Code and Reviewer Agents"
LABEL version="0.1.0"

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure git for container
RUN git config --global user.name "github-actions[bot]" && \
    git config --global user.email "github-actions[bot]@users.noreply.github.com" && \
    git config --global init.defaultBranch main && \
    git config --global --add safe.directory /app

# Install uv (pinned version for reproducibility)
RUN curl -LsSf https://astral.sh/uv/0.1.12/install.sh | sh && \
    ln -s /root/.cargo/bin/uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml ./
COPY README.md ./

# Install Python dependencies (without lock file for initial build)
# In production, use: uv sync --frozen with a committed lock file
RUN uv sync --no-dev

# Copy application code
COPY src/ ./src/

# Create directories
RUN mkdir -p .agent-state logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO
ENV LOG_FORMAT=json

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app'); import src; print('healthy')" || exit 1

# Default entrypoint
ENTRYPOINT ["uv", "run", "python", "-m", "src.code_agent.cli"]
CMD ["--help"]
