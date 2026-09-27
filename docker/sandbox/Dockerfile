# RANN Sandbox Container Image
# Production-ready execution environment for RANN projects
#
# Usage:
#   docker build -t rann-sandbox:latest .
#   docker run --rm -v /host/workspace:/workspace rann-sandbox:latest

FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -r rann && useradd -r -g rann rann

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    bash \
    jq \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install Python development tools
RUN pip install --no-cache-dir \
    python-dotenv==1.0.0 \
    rich==13.9.0 \
    && pip cache purge

# Set up workspace with correct ownership
WORKDIR /workspace
RUN chown -R rann:rann /workspace

# Switch to non-root user
USER rann

# Environment variables
ENV HOME=/workspace \
    PATH=/usr/local/bin:/usr/bin:/bin \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TERM=dumb

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command
CMD ["bash"]
