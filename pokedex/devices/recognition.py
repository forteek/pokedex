import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class RecognitionDependencyError(RuntimeError):
    """Raised when the selected inference runtime is not installed."""


@dataclass(frozen=True)
class PokemonRecognition:
    pokemon_id: int
    name: str
    confidence: float


class PokemonRecognizer(Protocol):
    def recognize(self, image_data: bytes) -> PokemonRecognition | None: ...


class OnnxPokemonRecognizer:
    """Lazy, quantized ONNX classifier for offline Pokémon image recognition."""

    INPUT_SIZE = (224, 224)
    EXPECTED_POKEMON_IDS = frozenset(range(1, 1025))

    def __init__(self, assets_dir: Path):
        self.model_path = assets_dir / "models" / "pokemon_classifier.onnx"
        self.labels_path = assets_dir / "models" / "pokemon_labels.json"
        self._session = None
        self._input_name: str | None = None
        self._labels: list[dict[str, object]] | None = None

    def recognize(self, image_data: bytes) -> PokemonRecognition | None:
        import cv2
        import numpy as np
        try:
            import onnxruntime as ort
        except ModuleNotFoundError as error:
            if error.name != "onnxruntime":
                raise
            raise RecognitionDependencyError(
                "Pokémon scanning needs ONNX Runtime; install project dependencies "
                "with `uv sync`."
            ) from error

        self._load(ort)
        image = cv2.imdecode(
            np.frombuffer(image_data, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if image is None:
            raise ValueError("Could not decode the captured photo")

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, self.INPUT_SIZE, interpolation=cv2.INTER_LINEAR)
        image = image.astype(np.float32) / 255.0
        image = (image - 0.5) / 0.5
        tensor = np.transpose(image, (2, 0, 1))[None, ...]

        output = self._session.run(None, {self._input_name: tensor})[0]
        logits = np.asarray(output).reshape(-1)
        labels = self._labels
        if labels is None or logits.size != len(labels):
            raise ValueError("Classifier output does not match its label file")
        best_index = int(np.argmax(logits))
        label = labels[best_index]
        pokemon_id = label.get("id")
        if pokemon_id is None:
            return None
        probability = self._softmax_probability(logits, best_index)
        return PokemonRecognition(
            pokemon_id=int(pokemon_id),
            name=str(label["name"]),
            confidence=probability,
        )

    def _load(self, ort) -> None:
        if self._session is not None:
            return
        if not self.model_path.is_file() or not self.labels_path.is_file():
            raise FileNotFoundError(
                "Pokémon recognition model files are missing from assets/models"
            )

        labels_data = json.loads(self.labels_path.read_text(encoding="utf-8"))
        if not isinstance(labels_data, list):
            raise ValueError("Pokémon model labels must be a JSON list")
        try:
            covered_ids = {
                int(label["id"])
                for label in labels_data
                if label.get("id") is not None
            }
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("Pokémon model labels contain an invalid entry") from error
        if covered_ids != self.EXPECTED_POKEMON_IDS:
            raise ValueError("Pokémon model labels must cover database IDs 1 through 1024")
        self._labels = labels_data

        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self._session = ort.InferenceSession(
            str(self.model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name

    @staticmethod
    def _softmax_probability(logits, index: int) -> float:
        import numpy as np

        shifted = logits - np.max(logits)
        probabilities = np.exp(shifted)
        return float(probabilities[index] / probabilities.sum())
