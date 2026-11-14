# Build from the repo root so the contracts are included:
#   docker build -f engine/Dockerfile -t fieldshift-engine .
FROM python:3.12-slim

WORKDIR /app
COPY contracts /app/contracts
COPY engine /app/engine
RUN pip install --no-cache-dir /app/engine

ENV FIELDSHIFT_CONTRACTS=/app/contracts
WORKDIR /app/engine
EXPOSE 8000
CMD ["uvicorn", "fieldshift.api:app", "--host", "0.0.0.0", "--port", "8000"]
