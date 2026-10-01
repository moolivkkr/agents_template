"""harness: the app-level names languages/python.md's ML block uses at module level (a small model, its
inputs, the feature extractor and the batch sink)."""
import numpy as np
import torch

model = torch.nn.Linear(4, 2)
data = [np.arange(4, dtype=np.float32) + i for i in range(70)]
processed: list[list[dict[str, object]]] = []


def extract_features(record: dict[str, object]) -> list[float]:
    return [float(len(str(record["id"])))]


def process(batch: tuple[dict[str, object], ...]) -> None:
    processed.append(list(batch))
