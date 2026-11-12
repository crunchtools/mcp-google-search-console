# MCP Google Search Console CrunchTools Container
# Built on Hummingbird Python image (Red Hat UBI-based) for enterprise security
#
# Build:
#   podman build -t quay.io/crunchtools/mcp-google-search-console .
#
# Run:
#   podman run --env-file ~/.config/mcp-env/mcp-google-search-console.env \
#     quay.io/crunchtools/mcp-google-search-console

# Stage 0: Lock (resolve the committed, Dependabot-maintained uv.lock to a
# pinned requirements file -- nothing in later stages is allowed to re-resolve)
FROM quay.io/hummingbird/python:3.14-builder AS lock
USER 0
RUN pip install --no-cache-dir uv==0.13.7
WORKDIR /lock
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project \
      --format requirements-txt -o /requirements.txt

# Stage 1: Builder (has a shell, dnf and build tools)
FROM quay.io/hummingbird/python:3.14-builder AS builder
USER 0
WORKDIR /app
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
COPY --from=lock /requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-deps -r /tmp/requirements.txt
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .

# Stage 2: Runtime (distroless -- no shell, no package manager)
FROM quay.io/hummingbird/python:3.14

# Labels for container metadata
LABEL name="mcp-google-search-console-crunchtools" \
      version="0.5.1" \
      summary="Secure MCP server for Google Search Console analytics, sitemaps, and URL inspection" \
      description="A security-focused MCP server for Google Search Console built on Red Hat UBI" \
      maintainer="crunchtools.com" \
      url="https://github.com/crunchtools/mcp-google-search-console" \
      io.k8s.display-name="MCP Google Search Console CrunchTools" \
      io.openshift.tags="mcp,google-search-console,seo" \
      org.opencontainers.image.source="https://github.com/crunchtools/mcp-google-search-console" \
      org.opencontainers.image.description="Secure MCP server for Google Search Console" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"

WORKDIR /app

COPY --from=builder /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Verify the install. Exec form: this stage has no /bin/sh for RUN's shell form.
RUN ["python3", "-c", "from mcp_google_search_console_crunchtools import main; print('Installation verified')"]

# Default: stdio transport (use -i with podman run)
# HTTP:    --transport streamable-http (use -d -p 8017:8017 with podman run)
EXPOSE 8017
ENTRYPOINT ["python", "-m", "mcp_google_search_console_crunchtools"]
