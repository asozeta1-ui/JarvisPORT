FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Models must be placed in the project root or set MODEL_DIR env var
# They are NOT copied into the image (too large for git)
# Place kokoro-v1.0.onnx and voices-v1.0.bin in the build context

EXPOSE 8080

CMD ["python", "server.py"]
