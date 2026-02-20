FROM python:3.11-slim

# Install from PyPI. Set MOCK_VERSION to pin (e.g. 0.1.6); omit for latest.
# PIP_DEFAULT_TIMEOUT=600 for slow networks (e.g. Raspberry Pi)
# PIP_INDEX_URL: use mirror for faster install, e.g. https://pypi.tuna.tsinghua.edu.cn/simple
ARG MOCK_VERSION=
ARG PIP_INDEX_URL=
ENV PIP_DEFAULT_TIMEOUT=600
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+--index-url ${PIP_INDEX_URL}} ai-protocol-mock${MOCK_VERSION:+==${MOCK_VERSION}} && mkdir -p /app/manifests

WORKDIR /app

ENV HTTP_PORT=4010
ENV MANIFEST_DIR=/app/manifests

EXPOSE 4010

# Sync manifests on startup, then run server
CMD sync-manifests --output-dir /app/manifests --force 2>/dev/null || true && \
    uvicorn ai_protocol_mock.main:app --host 0.0.0.0 --port ${HTTP_PORT}
