# languages/python.md "ML-Specific Patterns": the module ran its usage lines at import (gpu_scope +
# predict_batch on CPU, the generator pipeline over data.jsonl). Check what they produced, then the rest.
import numpy as np
import torch

from harness_stubs.ml_app import processed
from ml import pipeline as ml

assert len(ml.results) == 70 and ml.results[0].shape == (2,), (len(ml.results), ml.results[0].shape)
assert [len(b) for b in processed] == [1000, 500], [len(b) for b in processed]  # 1500 active of 3000 rows
assert processed[0][0] == {"id": 0, "features": [1.0]}, processed[0][0]
norm = ml.normalize(np.array([[1.0, 2.0], [3.0, 6.0]]))
assert np.allclose(norm.mean(axis=0), 0.0) and np.allclose(norm.std(axis=0), 1.0)
ml.set_seeds(7)
a = torch.rand(3)
ml.set_seeds(7)
assert torch.equal(a, torch.rand(3))  # seeded: reproducible
with ml.gpu_scope():  # no CUDA here: a no-op, not an error
    pass
cfg = ml.ExperimentConfig(model_name="m", learning_rate=0.1, batch_size=8, epochs=1)
assert cfg.to_artifact_path().parts[:2] == ("runs", "m"), cfg.to_artifact_path()
