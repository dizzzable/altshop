FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

WORKDIR /opt/remnashop

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-cache --compile-bytecode \
    && find .venv -type d -name "__pycache__" -exec rm -rf {} + \
    && rm -rf .venv/lib/python3.12/site-packages/pip* \
    && rm -rf .venv/lib/python3.12/site-packages/setuptools* \
    && rm -rf .venv/lib/python3.12/site-packages/wheel*

FROM python:3.12-alpine AS final

WORKDIR /opt/remnashop

COPY --from=builder /opt/remnashop/.venv /opt/remnashop/.venv

ENV PATH="/opt/remnashop/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/opt/remnashop

COPY ./src ./src
COPY ./assets /opt/remnashop/assets.default
COPY ./docker-entrypoint.sh ./docker-entrypoint.sh

# Convert CRLF to LF (in case file was copied from Windows) and make executable
RUN sed -i 's/\r$//' ./docker-entrypoint.sh && chmod +x ./docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]
