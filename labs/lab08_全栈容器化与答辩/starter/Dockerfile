# Lab08 starter, minimal backend image (teaching)
# Mirrors deploy-demo/Dockerfile.backend: python:3.12-slim, selective COPY, layer-cache friendly
FROM python:3.12-slim
WORKDIR /app

# System deps for soundfile/librosa (libsndfile1), keep layer cache friendly
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Layer-cache: copy dependency manifest first, so pip layer is cacheable
COPY pyproject.toml README.md ./
COPY m2t/ ./m2t/

# Install teaching package (m2t) + runtime deps, no wheel cache
RUN pip install --no-cache-dir -e .

ENV MTT_DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "-m", "m2t.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
