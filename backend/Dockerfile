FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MODEL_DIR=/app/models DATA_DIR=/app/data
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app/backend
ARG INSTALL_LOCAL_MEDIA=true
RUN if [ "$INSTALL_LOCAL_MEDIA" = "true" ]; then python -m backend.install_models; fi
RUN useradd --create-home app && mkdir -p /app/data /app/models && chown -R app:app /app/data /app/models
USER app
EXPOSE 8000
# One process avoids duplicate reminder schedulers and duplicate speech models.
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
