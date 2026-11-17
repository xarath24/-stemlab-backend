import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "1")
os.environ.setdefault("TF_NUM_INTEROP_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import logging, shutil, threading, time, uuid
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("stem-lab")
APP_DIR = Path(__file__).resolve().parent
JOBS_DIR = Path(os.getenv("JOBS_DIR", str(APP_DIR / "jobs")))
JOBS_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
JOB_TTL_HOURS = int(os.getenv("JOB_TTL_HOURS", "12"))

MODELS = {"2stems": "spleeter:2stems", "4stems": "spleeter:4stems", "5stems": "spleeter:5stems"}
ORDER = {
    "2stems": ["vocals", "accompaniment"],
    "4stems": ["vocals", "drums", "bass", "other"],
    "5stems": ["vocals", "drums", "bass", "piano", "other"],
}
EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".aiff", ".aif", ".opus"}
MIME_EXT = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav",
            "audio/x-wav": ".wav", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
            "audio/flac": ".flac", "audio/ogg": ".ogg", "audio/aac": ".aac"}
cache: Dict[str, object] = {}
inference_lock = threading.Lock()

app = FastAPI(title="STEM LAB Audio Separation API",
              description="Pemisahan audio 2, 4, dan 5 stem menggunakan Spleeter.",
              version="1.0.0")
raw_origins = os.getenv("CORS_ORIGINS", "*").strip()
origins = ["*"] if raw_origins == "*" else [x.strip() for x in raw_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])

def cleanup_jobs():
    cutoff = time.time() - JOB_TTL_HOURS * 3600
    for folder in JOBS_DIR.iterdir():
        try:
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass

def get_separator(mode):
    if mode not in cache:
        from spleeter.separator import Separator
        logger.info("Loading model %s", MODELS[mode])
        cache[mode] = Separator(MODELS[mode])
    return cache[mode]

@app.get("/")
def root():
    return {"service": "STEM LAB Audio Separation API", "status": "online",
            "health": "/health", "docs": "/docs", "supported_modes": list(MODELS)}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "stem-lab-backend",
            "supported_modes": list(MODELS), "max_upload_mb": MAX_UPLOAD_MB}

@app.post("/api/v1/separate")
def separate_audio(file: UploadFile = File(...),
                   stems: str = Query("2stems", pattern="^(2stems|4stems|5stems)$"),
                   format: str = Query("wav")):
    if stems not in MODELS:
        raise HTTPException(400, "Mode harus 2stems, 4stems, atau 5stems.")
    if format.lower() != "wav":
        raise HTTPException(400, "Format output yang didukung hanya wav.")

    original = Path(file.filename or "audio").name
    ext = Path(original).suffix.lower()
    if ext not in EXTS:
        ext = MIME_EXT.get((file.content_type or "").lower(), ext or ".mp3")
        if ext not in EXTS:
            raise HTTPException(415, "Format audio tidak didukung.")
    job_id = uuid.uuid4().hex
    job = JOBS_DIR / job_id
    raw = job / "raw"
    downloads = job / "downloads"
    raw.mkdir(parents=True)
    downloads.mkdir(parents=True)
    source = job / ("input" + ext)
    started = time.time()

    try:
        total = 0
        with source.open("wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, f"Ukuran file melebihi batas {MAX_UPLOAD_MB} MB.")
                out.write(chunk)
        if total == 0:
            raise HTTPException(400, "File audio kosong.")

        cleanup_jobs()
        # Inference is serialized to reduce peak RAM usage on small Railway instances.
        with inference_lock:
            separator = get_separator(stems)
            logger.info("Processing job %s (%s, %s bytes)", job_id, stems, total)
            separator.separate_to_file(str(source), str(raw), codec="wav", bitrate="128k")

        found = {p.stem.lower(): p for p in raw.rglob("*.wav")}
        missing = [name for name in ORDER[stems] if name not in found]
        if missing:
            raise RuntimeError("Track tidak lengkap dari Spleeter: " + ", ".join(missing))

        output_files = []
        for name in ORDER[stems]:
            filename = name + ".wav"
            shutil.copy2(found[name], downloads / filename)
            output_files.append(filename)

        return {"success": True, "job_id": job_id, "output_files": output_files,
                "processing_time": round(time.time() - started, 2),
                "mode": stems, "format": "wav"}

    except HTTPException:
        shutil.rmtree(job, ignore_errors=True)
        raise
    except Exception as exc:
        logger.exception("Separation failed for job %s", job_id)
        shutil.rmtree(job, ignore_errors=True)
        detail = str(exc).strip() or exc.__class__.__name__
        raise HTTPException(500, "Pemisahan audio gagal: " + detail[:350])
    finally:
        try:
            file.file.close()
        except Exception:
            pass

@app.get("/api/v1/separate/{job_id}/download/{filename}")
def download_stem(job_id: str, filename: str):
    if not job_id.isalnum() or len(job_id) != 32:
        raise HTTPException(404, "Job tidak ditemukan.")
    safe = Path(filename).name
    if safe != filename or not safe.lower().endswith(".wav"):
        raise HTTPException(400, "Nama file tidak valid.")
    target = JOBS_DIR / job_id / "downloads" / safe
    if not target.is_file():
        raise HTTPException(404, "File hasil tidak ditemukan atau sudah kedaluwarsa.")
    return FileResponse(str(target), media_type="audio/wav", filename=safe)
