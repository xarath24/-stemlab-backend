FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES=-1 TF_CPP_MIN_LOG_LEVEL=2 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 OMP_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && pip install --no-cache-dir -r requirements.txt
COPY main.py .
RUN mkdir -p /app/jobs
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
