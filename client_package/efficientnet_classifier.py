"""EfficientNet-B0 ImageNet probe powered by OpenCV DNN.

The bundled checkpoint is the official ImageNet-1K model.  It is useful as a
lightweight visual backbone and for validating the local inference path, but it
does *not* contain a game/non-game head.  Callers must therefore treat the
result as diagnostic evidence only until a project-specific checkpoint has
been fine-tuned and evaluated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import threading
import time
from typing import Iterable

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "efficientnet_b0"


@dataclass(frozen=True)
class ImageNetPrediction:
    index: int
    label: str
    probability: float


@dataclass(frozen=True)
class EfficientNetProbeResult:
    model: str
    model_task: str
    game_classification: str
    latency_ms: float
    top_k: tuple[ImageNetPrediction, ...]
    note: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["top_k"] = [asdict(item) for item in self.top_k]
        return payload


def _softmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32).reshape(-1)
    shifted = values - float(values.max())
    exp = np.exp(shifted)
    return exp / float(exp.sum())


class EfficientNetB0Probe:
    """Run the bundled EfficientNet-B0 checkpoint without changing activity.

    OpenCV DNN loads the ONNX graph and its external ``.data`` weights.  The
    model itself performs ImageNet mean/std normalization, so preprocessing
    here only converts BGR to RGB, resizes/crops, and scales pixels to [0, 1].
    """

    def __init__(self, model_dir: str | Path = DEFAULT_MODEL_DIR):
        self.model_dir = Path(model_dir)
        self.model_path = self.model_dir / "efficientnet_b0_opencv.onnx"
        self.labels_path = self.model_dir / "labels.txt"
        self._net = None
        self._labels: tuple[str, ...] = ()
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._net is not None:
            return
        if not self.model_path.is_file():
            raise FileNotFoundError(f"EfficientNet-B0 model not found: {self.model_path}")
        if not self.labels_path.is_file():
            raise FileNotFoundError(f"ImageNet labels not found: {self.labels_path}")

        labels = tuple(
            line.strip() for line in self.labels_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if len(labels) != 1000:
            raise ValueError(f"expected 1000 ImageNet labels, got {len(labels)}")

        net = cv2.dnn.readNetFromONNX(str(self.model_path))
        self._labels = labels
        self._net = net

    @staticmethod
    def _preprocess(image_bgr: np.ndarray) -> np.ndarray:
        if image_bgr is None or image_bgr.size == 0:
            raise ValueError("image is empty")
        if image_bgr.ndim != 3 or image_bgr.shape[2] not in (3, 4):
            raise ValueError(f"expected BGR/BGRA image, got shape {image_bgr.shape}")
        if image_bgr.shape[2] == 4:
            image_bgr = cv2.cvtColor(image_bgr, cv2.COLOR_BGRA2BGR)

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        height, width = image_rgb.shape[:2]
        scale = 256.0 / min(height, width)
        resized = cv2.resize(
            image_rgb,
            (int(round(width * scale)), int(round(height * scale))),
            interpolation=cv2.INTER_CUBIC,
        )
        top = max(0, (resized.shape[0] - 224) // 2)
        left = max(0, (resized.shape[1] - 224) // 2)
        crop = resized[top:top + 224, left:left + 224]
        if crop.shape[:2] != (224, 224):
            raise ValueError(f"failed to create 224x224 center crop: {crop.shape}")

        tensor = crop.astype(np.float32) / 255.0
        return np.ascontiguousarray(tensor.transpose(2, 0, 1)[None, ...])

    def predict_topk(self, image_bgr: np.ndarray, top_k: int = 5) -> tuple[tuple[ImageNetPrediction, ...], float]:
        if top_k < 1 or top_k > 1000:
            raise ValueError("top_k must be between 1 and 1000")
        self._ensure_loaded()
        blob = self._preprocess(image_bgr)

        started = time.perf_counter()
        # A single cv2.dnn.Net is not documented as safe for concurrent calls.
        with self._lock:
            self._net.setInput(blob)
            logits = self._net.forward()
        latency_ms = (time.perf_counter() - started) * 1000.0

        probabilities = _softmax(logits)
        indices: Iterable[int] = np.argsort(probabilities)[-top_k:][::-1]
        predictions = tuple(
            ImageNetPrediction(
                index=int(index),
                label=self._labels[int(index)],
                probability=round(float(probabilities[int(index)]), 6),
            )
            for index in indices
        )
        return predictions, round(latency_ms, 3)

    def inspect(self, image_bgr: np.ndarray, top_k: int = 5) -> EfficientNetProbeResult:
        predictions, latency_ms = self.predict_topk(image_bgr, top_k=top_k)
        return EfficientNetProbeResult(
            model="EfficientNet-B0 ImageNet-1K",
            model_task="object_classification",
            game_classification="uncertain",
            latency_ms=latency_ms,
            top_k=predictions,
            note=(
                "The bundled checkpoint has 1000 ImageNet object classes but no "
                "game/non-game output. Fine-tuning and a labeled validation set are "
                "required before it may affect activity classification."
            ),
        )
