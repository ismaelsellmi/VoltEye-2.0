"""La détection au fil de l'eau de la passerelle donne les mêmes événements que la détection hors ligne."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edge.gateway import StreamingDetector  # noqa: E402
from volteye.stream import detect_events  # noqa: E402


def test_streaming_matches_batch_detection():
    rng = np.random.default_rng(3)
    levels = np.repeat(rng.choice([0, 5, 12, 20, 31], size=40), rng.integers(5, 60, size=40))
    p = levels + rng.normal(0, 0.15, len(levels))
    batch, _ = detect_events(p)
    det = StreamingDetector()
    online = [hit[0] for x in p if (hit := det.push(x))]
    assert online == batch[:len(online)] and len(batch) - len(online) <= 1   # le dernier peut manquer (fin du flux)


def test_no_event_on_flat_signal():
    det = StreamingDetector()
    assert not any(det.push(x) for x in np.full(200, 12.0) + np.random.default_rng(0).normal(0, 0.1, 200))
