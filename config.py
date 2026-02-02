"""Конфигурация приложения."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent 
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
MODELS_DIR = BASE_DIR / "models"  
DB_PATH = BASE_DIR / "data" / "history.db"
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

_model_candidates = [
    MODELS_DIR / "weapon_yolov8.pt",
    MODELS_DIR / "best.pt",
]
MODEL_PATH = os.environ.get("WEAPON_MODEL") or next(
    (str(p) for p in _model_candidates if p.exists()),
    str(MODELS_DIR / "weapon_yolov8.pt"),
)
FALLBACK_MODEL = "yolov8s.pt"  # COCO - для демо, без оружия

CONF_THRESHOLD = float(os.environ.get("CONF_THRESHOLD", "0.45"))
CONF_THRESHOLD_LOW = float(os.environ.get("CONF_THRESHOLD_LOW", "0.30"))
IOU_THRESHOLD = float(os.environ.get("IOU_THRESHOLD", "0.45"))
IMPROVE_ON_MISS = os.environ.get("IMPROVE_ON_MISS", "true").lower() in ("1", "true", "yes")

WEAPON_CLASSES = [
    "gun", "pistol", "rifle", "knife", "handgun", "shotgun",
    "sword", "weapon", "firearm", "blade"
]

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
