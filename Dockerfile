FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        libgl1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY frontend frontend
COPY run.py run.py

ENV ZELVERA_DATA_DIR=/data
ENV ZELVERA_HOST=0.0.0.0
ENV ZELVERA_PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

VOLUME /data

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=8 \
    CMD curl -fsS http://127.0.0.1:8000/api/auth/status || exit 1

CMD ["python", "run.py"]
