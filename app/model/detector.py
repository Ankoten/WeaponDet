import time
from pathlib import Path
from typing import Any

from app.config import (
    CONF_THRESHOLD,
    CONF_THRESHOLD_LOW,
    FALLBACK_MODEL,
    IMPROVE_ON_MISS,
    IOU_THRESHOLD,
    MODEL_PATH,
    WEAPON_CLASSES,
)


class WeaponDetector:
    def __init__(self):
        self._model = None
        self._model_loaded = False
        self._class_names = {}

    def _load_model(self) -> None:
        if self._model_loaded:
            return
        try:
            from ultralytics import YOLO

            path = Path(MODEL_PATH)
            if path.exists():
                self._model = YOLO(str(path))
                self._class_names = dict(self._model.names)
            else:
                self._model = YOLO(FALLBACK_MODEL)
                self._class_names = dict(self._model.names)
            self._model_loaded = True
        except Exception as e:
            raise RuntimeError(f"Не удалось загрузить модель: {e}") from e

    def _is_weapon_class(self, class_name: str) -> bool:
        name_lower = str(class_name).lower()
        return any(w in name_lower for w in WEAPON_CLASSES)

    def _extract_detections(self, results, filter_weapons_only: bool) -> list[dict]:
        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            class_name = self._class_names.get(cls_id, f"class_{cls_id}")
            if filter_weapons_only and not self._is_weapon_class(class_name):
                continue
            detections.append({
                "class": class_name,
                "confidence": round(conf, 4),
                "bbox": [round(x, 2) for x in xyxy],
            })
        return detections

    def detect(self, image_path: str, filter_weapons_only: bool = True) -> dict[str, Any]:
        self._load_model()
        start = time.perf_counter()

        results = self._model.predict(
            source=image_path,
            conf=CONF_THRESHOLD,
            iou=IOU_THRESHOLD,
            verbose=False,
        )[0]
        detections = self._extract_detections(results, filter_weapons_only)

        if not detections and IMPROVE_ON_MISS:
            results = self._model.predict(
                source=image_path,
                conf=CONF_THRESHOLD_LOW,
                iou=IOU_THRESHOLD,
                augment=True,
                verbose=False,
            )[0]
            detections = self._extract_detections(results, filter_weapons_only)

        elapsed_ms = (time.perf_counter() - start) * 1000

        annotated_path = None
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is not None:
                for det in detections:
                    x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    label = f"{det['class']} {det['confidence']:.2f}"
                    cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                out_path = Path(image_path).parent / f"annotated_{Path(image_path).name}"
                cv2.imwrite(str(out_path), img)
                annotated_path = str(out_path)
        except Exception:
            pass

        return {
            "detections": detections,
            "detections_count": len(detections),
            "processing_time_ms": round(elapsed_ms, 2),
            "annotated_image": annotated_path,
            "class_names": list(self._class_names.values()),
        }

    def detect_video(
        self,
        video_path: str,
        filter_weapons_only: bool = True,
        max_frames: int = 60,
        frames_per_second: float = 1.0,
    ) -> dict[str, Any]:
        import cv2
        self._load_model()
        start = time.perf_counter()

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()

        frame_interval = max(1, int(fps / frames_per_second))
        frame_indices = list(range(0, total_frames, frame_interval))[:max_frames]
        if not frame_indices:
            frame_indices = [0]

        all_detections: list[dict] = []
        frames_with_detections = 0
        best_frame_idx: int | None = None
        best_frame_det_count = 0
        best_annotated_path: str | None = None
        parent_dir = Path(video_path).parent
        stem = Path(video_path).stem
        temp_files: list[Path] = []

        for frame_no in frame_indices:
            cap = cv2.VideoCapture(video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                continue

            frame_path = parent_dir / f"{stem}_tmp_f{frame_no}.jpg"
            cv2.imwrite(str(frame_path), frame)
            temp_files.append(frame_path)

            result = self.detect(str(frame_path), filter_weapons_only)

            dets = result.get("detections", [])
            for d in dets:
                d["frame_no"] = frame_no
                d["time_sec"] = round(frame_no / fps, 1)
            all_detections.extend(dets)
            if dets:
                frames_with_detections += 1
                if len(dets) > best_frame_det_count:
                    best_frame_det_count = len(dets)
                    best_frame_idx = frame_no
                    best_annotated_path = result.get("annotated_image")

        for p in temp_files:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

        if not best_annotated_path and frame_indices:
            cap = cv2.VideoCapture(video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_indices[0])
            ret, frame = cap.read()
            cap.release()
            if ret:
                sample_path = parent_dir / f"{stem}_sample.jpg"
                cv2.imwrite(str(sample_path), frame)
                r = self.detect(str(sample_path), filter_weapons_only)
                best_annotated_path = r.get("annotated_image")
                try:
                    sample_path.unlink(missing_ok=True)
                except Exception:
                    pass

        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "detections": all_detections,
            "detections_count": len(all_detections),
            "processing_time_ms": round(elapsed_ms, 2),
            "annotated_image": best_annotated_path,
            "class_names": list(self._class_names.values()),
            "processed_frames": len(frame_indices),
            "total_frames": total_frames,
            "frames_with_detections": frames_with_detections,
            "fps": round(fps, 1),
        }

    def detect_frame(self, frame_bytes: bytes, filter_weapons_only: bool = True) -> dict[str, Any]:
        import tempfile
        import cv2
        import numpy as np

        nparr = np.frombuffer(frame_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"detections": [], "detections_count": 0, "processing_time_ms": 0}

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            cv2.imwrite(f.name, img)
            return self.detect(f.name, filter_weapons_only)
