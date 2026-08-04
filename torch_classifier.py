import logging
from pathlib import Path

from ..config import settings
from .features import CLASS_LABELS
from .sequence import SEQ_CHANNELS, SEQ_LEN, build_sequence

log = logging.getLogger(__name__)


def build_network(n_classes: int = 3, hidden: int = 48, layers: int = 2):
    """
    A two-layer GRU over the report sequence.
    """
    import torch.nn as nn

    class TrackGRU(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.gru = nn.GRU(
                input_size=len(SEQ_CHANNELS),
                hidden_size=hidden,
                num_layers=layers,
                batch_first=True,
                dropout=0.15 if layers > 1 else 0.0,
            )
            self.head = nn.Sequential(
                nn.LayerNorm(hidden),
                nn.Linear(hidden, n_classes),
            )

        def forward(self, x):
            # x: (batch, SEQ_LEN, channels). 
            
            output, _ = self.gru(x)
            return self.head(output[:, -1])

    return TrackGRU()


class TorchTrackClassifier:
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = Path(model_path or settings.torch_model_path)
        self.model = None
        self.labels: list[str] = CLASS_LABELS
        self.load()

    # ---------------------------------------------------------------- load
    def load(self) -> bool:
        if not self.model_path.exists():
            log.warning(
                "No PyTorch model at %s. Train one with "
                "`python -m app.ml.train_torch`, or set "
                "CLASSIFIER_BACKEND=sklearn to use the random forest.",
                self.model_path,
            )
            self.model = None
            return False
        try:
            import torch

            bundle = torch.load(self.model_path, map_location="cpu", weights_only=False)
            self.labels = list(bundle["labels"])
            network = build_network(
                n_classes=len(self.labels),
                hidden=bundle.get("hidden", 48),
                layers=bundle.get("layers", 2),
            )
            network.load_state_dict(bundle["state_dict"])
            network.eval()
            self.model = network
            log.info("Loaded PyTorch classifier from %s", self.model_path)
            return True
        except Exception:
            log.exception("Could not load the PyTorch model.")
            self.model = None
            return False

    @property
    def ready(self) -> bool:
        return self.model is not None

    # ------------------------------------------------------------- predict
    def predict(self, samples: list[dict]) -> tuple[str, float]:
        if self.model is None:
            return "unknown", 0.0
        if len(samples) < settings.min_points_for_classification:
            return "unknown", 0.0

        steps = build_sequence(samples)
        if not steps:
            return "unknown", 0.0

        try:
            import torch

            with torch.no_grad():
                batch = torch.tensor([steps], dtype=torch.float32)
                probabilities = torch.softmax(self.model(batch), dim=1)[0]
                index = int(probabilities.argmax())
            return self.labels[index], float(probabilities[index])
        except Exception:
            log.exception("PyTorch prediction failed.")
            return "unknown", 0.0

    def info(self) -> dict:
        return {
            "ready": self.ready,
            "backend": "pytorch",
            "path": str(self.model_path),
            "kind": "GRU sequence classifier" if self.model else "not loaded",
            "sequence_length": SEQ_LEN,
            "channels": SEQ_CHANNELS,
            "labels": self.labels,
        }
