import logging
from pathlib import Path

from ..config import settings
from .explain import explain_forest, explain_rule, summarise
from .features import CLASS_LABELS, FEATURE_NAMES, extract_features

log = logging.getLogger(__name__)


class TrackClassifier:
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = Path(model_path or settings.model_path)
        self.model = None
        self.labels: list[str] = CLASS_LABELS
        self.load()

    # ---------------------------------------------------------------- load
    def load(self) -> bool:
        if not self.model_path.exists():
            log.warning(
                "No model at %s — using the fallback rule. "
                "Run `python -m app.ml.train` to train one.",
                self.model_path,
            )
            return False
        try:
            import joblib

            bundle = joblib.load(self.model_path)
            self.model = bundle["model"]
            self.labels = list(bundle.get("labels", CLASS_LABELS))
            log.info("Loaded classifier from %s", self.model_path)
            return True
        except Exception:  # pragma: no cover - defensive
            log.exception("Could not load the model; falling back to the rule.")
            self.model = None
            return False

    @property
    def ready(self) -> bool:
        return self.model is not None

    # ------------------------------------------------------------ predict
    def predict(self, samples: list[dict]) -> tuple[str, float]:
        """Return (label, confidence 0–1) for one track's recent history."""
        if len(samples) < settings.min_points_for_classification:
            return "unknown", 0.0

        features = extract_features(samples)

        if self.model is None:
            return self._fallback(features)

        try:
            import numpy as np

            proba = self.model.predict_proba(np.array([features], dtype=float))[0]
            idx = int(proba.argmax())
            return str(self.model.classes_[idx]), float(proba[idx])
        except Exception:  # pragma: no cover - defensive
            log.exception("Prediction failed; using the fallback rule.")
            return self._fallback(features)

    # ----------------------------------------------------------- fallback
    @staticmethod
    def _fallback(features: list[float]) -> tuple[str, float]:
        """A readable stand-in so the dashboard is never blank."""
        f = dict(zip(FEATURE_NAMES, features))
        if f["rssi_std"] > 9 and f["mean_rssi_dbm"] < -78:
            return "clutter", 0.55
        if f["heading_std_deg"] > 22 and f["mean_speed_mps"] < 16:
            return "bird", 0.55
        return "drone", 0.55

    # -------------------------------------------------------- predict_many
    def predict_many(self, batch: list[list[dict]]) -> list[tuple[str, float]]:
        results: list[tuple[str, float]] = [("unknown", 0.0)] * len(batch)
        if not batch:
            return results

        rows, positions = [], []
        for i, samples in enumerate(batch):
            if len(samples) >= settings.min_points_for_classification:
                rows.append(extract_features(samples))
                positions.append(i)

        if not rows:
            return results

        if self.model is None:
            for i, row in zip(positions, rows):
                results[i] = self._fallback(row)
            return results

        try:
            import numpy as np

            probabilities = self.model.predict_proba(np.array(rows, dtype=float))
            for i, proba in zip(positions, probabilities):
                index = int(proba.argmax())
                results[i] = (str(self.model.classes_[index]), float(proba[index]))
        except Exception:
            log.exception("Batch prediction failed; using the fallback rule.")
            for i, row in zip(positions, rows):
                results[i] = self._fallback(row)

        return results

    # ------------------------------------------------------------ explain
    def explain(self, samples: list[dict], label: str) -> list[dict]:
        """
        Why this track got this verdict.

        Returns the features that moved the decision most, each with the value
        observed and a checkable sentence. Empty while the track is too young
        to classify.
        """
        if label == "unknown" or len(samples) < settings.min_points_for_classification:
            return []

        features = extract_features(samples)
        if self.model is None:
            return explain_rule(features, label)
        try:
            return explain_forest(self.model, features, label)
        except Exception:
            log.exception("Could not build evidence; falling back to the rule view.")
            return explain_rule(features, label)

    @staticmethod
    def summarise(label: str, confidence: float, evidence: list[dict]) -> str:
        return summarise(label, confidence, evidence)

    def info(self) -> dict:
        return {
            "ready": self.ready,
            "explainable": True,
            "explain_method": "decision-path decomposition"
            if self.model
            else "rule inspection",
            "path": str(self.model_path),
            "kind": type(self.model).__name__ if self.model else "rule-based fallback",
            "features": FEATURE_NAMES,
            "labels": self.labels,
        }


def build_classifier():
    """Pick a backend from settings. Both expose the same four methods."""
    if settings.classifier_backend.lower() == "torch":
        try:
            from .torch_classifier import TorchTrackClassifier

            return TorchTrackClassifier()
        except ImportError:
            log.warning(
                "CLASSIFIER_BACKEND=torch but PyTorch isn't installed. "
                "Falling back to the random forest. "
                "Install it with: pip install -r requirements-torch.txt"
            )
    return TrackClassifier()


classifier = build_classifier()
