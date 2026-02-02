import base64
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import BASE_DIR, MAX_UPLOAD_SIZE, OUTPUT_DIR, UPLOAD_DIR
from app.model.detector import WeaponDetector
from app.reports.generator import generate_excel, generate_pdf
from app.storage.history import export_json, get_history, get_stats, save_query

app = FastAPI(title="Weapon Detection API", version="1.0.0")
detector = WeaponDetector()

(BASE_DIR / "static").mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class ProcessResult(BaseModel):
    detections: list
    detections_count: int
    processing_time_ms: float
    annotated_image_b64: str | None
    query_id: str
    processed_frames: int | None = None
    total_frames: int | None = None
    frames_with_detections: int | None = None
    fps: float | None = None


class CameraFrame(BaseModel):
    frame_b64: str


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/process/image", response_model=ProcessResult)
async def process_image(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"Файл слишком большой. Макс: {MAX_UPLOAD_SIZE // (1024*1024)} MB")
    ext = Path(file.filename or "img").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        raise HTTPException(400, "Поддерживаются только изображения: jpg, png, bmp, webp")
    dest = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    dest.write_bytes(content)
    result = detector.detect(str(dest), filter_weapons_only=False)
    annotated_b64 = None
    if result.get("annotated_image"):
        ap = Path(result["annotated_image"])
        if ap.exists():
            annotated_b64 = base64.b64encode(ap.read_bytes()).decode()
    qid = save_query(source="upload", filename=file.filename, detections=result["detections"], processing_time_ms=result["processing_time_ms"])
    return ProcessResult(detections=result["detections"], detections_count=result["detections_count"], processing_time_ms=result["processing_time_ms"], annotated_image_b64=annotated_b64, query_id=qid)


@app.post("/api/process/frame", response_model=ProcessResult)
async def process_frame(data: CameraFrame):
    try:
        frame_bytes = base64.b64decode(data.frame_b64)
    except Exception:
        raise HTTPException(400, "Неверный формат base64")
    result = detector.detect_frame(frame_bytes, filter_weapons_only=False)
    annotated_b64 = None
    if result.get("annotated_image"):
        ap = Path(result["annotated_image"])
        if ap.exists():
            annotated_b64 = base64.b64encode(ap.read_bytes()).decode()
    qid = save_query(source="camera", filename=None, detections=result["detections"], processing_time_ms=result["processing_time_ms"])
    return ProcessResult(detections=result["detections"], detections_count=result["detections_count"], processing_time_ms=result["processing_time_ms"], annotated_image_b64=annotated_b64, query_id=qid)


@app.post("/api/process/video", response_model=ProcessResult)
async def process_video(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"Файл слишком большой. Макс: {MAX_UPLOAD_SIZE // (1024*1024)} MB")
    ext = Path(file.filename or "vid").suffix.lower()
    if ext not in (".mp4", ".avi", ".mov", ".webm", ".mkv"):
        raise HTTPException(400, "Поддерживаются видео: mp4, avi, mov, webm, mkv")
    dest = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    dest.write_bytes(content)
    result = detector.detect_video(str(dest), filter_weapons_only=False, max_frames=60, frames_per_second=1.0)
    annotated_b64 = None
    if result.get("annotated_image"):
        ap = Path(result["annotated_image"])
        if ap.exists():
            annotated_b64 = base64.b64encode(ap.read_bytes()).decode()
    qid = save_query(source="video", filename=file.filename, detections=result["detections"], processing_time_ms=result["processing_time_ms"])
    return ProcessResult(
        detections=result["detections"], detections_count=result["detections_count"], processing_time_ms=result["processing_time_ms"],
        annotated_image_b64=annotated_b64, query_id=qid,
        processed_frames=result.get("processed_frames"), total_frames=result.get("total_frames"),
        frames_with_detections=result.get("frames_with_detections"), fps=result.get("fps"),
    )


@app.get("/api/history")
async def api_history(limit: int = 100, offset: int = 0):
    return {"history": get_history(limit=limit, offset=offset)}


@app.get("/api/stats")
async def api_stats():
    return get_stats()


@app.get("/api/export/json")
async def export_history_json():
    path = export_json(OUTPUT_DIR / "history_export.json")
    return FileResponse(str(path), filename=path.name, media_type="application/json")


@app.get("/api/export/pdf")
async def export_pdf():
    path = generate_pdf()
    return FileResponse(str(path), filename=path.name, media_type="application/pdf")


@app.get("/api/export/excel")
async def export_excel():
    path = generate_excel()
    return FileResponse(str(path), filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
