FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/
COPY scripts/ scripts/
RUN mkdir -p manifests

ENV HTTP_PORT=4010
ENV MANIFEST_DIR=/app/manifests

EXPOSE 4010

# Sync manifests on startup, then run server
CMD python scripts/sync_manifests.py --force 2>/dev/null || true && \
    uvicorn ai_protocol_mock.main:app --host 0.0.0.0 --port ${HTTP_PORT}
