# Exact `3.12.15` Docker base images/downloads are not available upstream here;
# pin current `3.12` images by digest for reproducible Docker builds.
FROM ghcr.io/astral-sh/uv:python3.12-alpine@sha256:11ed51ffb1b203111052aae80a997a399788d55515dbbe5c0895d5ddff23c6d4 AS builder

WORKDIR /opt/altshop

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-cache --compile-bytecode \
    && find .venv -type d -name "__pycache__" -exec rm -rf {} + \
    && rm -rf .venv/lib/python3.12/site-packages/pip* \
    && rm -rf .venv/lib/python3.12/site-packages/setuptools* \
    && rm -rf .venv/lib/python3.12/site-packages/wheel*

FROM python:3.12-alpine@sha256:7747d47f92cfca63a6e2b50275e23dba8407c30d8ae929a88ddd49a5d3f2d331 AS final

WORKDIR /opt/altshop

COPY --from=builder /opt/altshop/.venv /opt/altshop/.venv

ENV PATH="/opt/altshop/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/opt/altshop

COPY ./src ./src
COPY ./assets /opt/altshop/assets.default
COPY ./docker-entrypoint.sh ./docker-entrypoint.sh

# Convert CRLF to LF (in case file was copied from Windows) and make executable
RUN sed -i 's/\r$//' ./docker-entrypoint.sh && chmod +x ./docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]
