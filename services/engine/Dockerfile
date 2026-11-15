FROM ghcr.io/astral-sh/uv:0.9.5 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /bin/uv
WORKDIR /app
COPY packages/contracts/schemas /app/packages/contracts/schemas
COPY packages/contracts/examples /app/packages/contracts/examples
COPY services/engine /app/services/engine
ENV CROPPILOT_CONTRACTS=/app/packages/contracts UV_LINK_MODE=copy
WORKDIR /app/services/engine
RUN uv sync --frozen --no-dev --no-editable && useradd --system --uid 1001 engine
USER engine
EXPOSE 8000
CMD [".venv/bin/uvicorn", "fieldshift.api:app", "--host", "0.0.0.0", "--port", "8000"]
