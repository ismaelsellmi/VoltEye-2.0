"""Tests de l'assistant énergie, du serveur MCP et des explications (Grad-CAM, intervalles conformes)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")

from agent import assistant, tools  # noqa: E402
from agent.evaluate import correct, numbers  # noqa: E402


def test_machine_and_month_parsing():
    assert tools.machine_key("Compresseur d'air") == "compresseur"
    assert tools.machine_key("la climatisation") == "cvc"
    assert tools.month_key("février") == "2026-02" and tools.month_key("novembre") == "2025-11"
    with pytest.raises(ValueError):
        tools.machine_key("grue")


@pytest.mark.parametrize("question,tool", [
    ("Combien la fuite d'air de février nous a-t-elle coûté ?", "anomalies"),
    ("Combien a coûté la veille de la CNC en septembre ?", "anomalies"),
    ("Quel est l'état de santé du convoyeur ?", "sante"),
    ("Combien de MW VoltEye Grid efface-t-il ?", "voltEye_grid"),
    ("Combien consomme l'atelier la nuit ?", "hors_production"),
    ("Comment réparer une fuite d'air comprimé ?", "recherche_documentation"),
    ("De combien le planning réduit-il la facture ?", "planning"),
])
def test_offline_routing(question, tool):
    assert assistant.route(question)[0] == tool


def test_number_matching():
    assert numbers("F1 0,82 et 1 234,5 kWh") == [1.0, 0.82, 1234.5]
    assert correct("Coût : 263,5 TND", 263.5) and not correct("Coût : 26,3 TND", 263.5)
    assert correct("détecteur à ultrasons", "ultrasons")


def test_conformal_interval_covers_target():
    from volteye.forecasting import ConformalInterval
    rng = np.random.default_rng(0)
    idx = pd.date_range("2026-01-01", periods=24 * 200, freq="h")
    x = pd.DataFrame({"heure": idx.hour, "production": ((idx.hour >= 6) & (idx.hour < 22)).astype(int)}, index=idx)
    y = pd.Series(10 + 40 * x["production"] + rng.normal(0, 3, len(idx)), index=idx)
    split = idx[24 * 150]
    ci = ConformalInterval().fit(x[idx < split], y[idx < split])
    lo, hi = ci.predict(x[idx >= split])
    cover = ((y[idx >= split] >= lo) & (y[idx >= split] <= hi)).mean()
    assert 0.75 <= cover <= 0.95


def test_gradcam_shape_and_range():
    pytest.importorskip("torch")
    from volteye import config as C
    from volteye.explain import gradcam
    from volteye.recognition import Recognizer, event_waveform
    from volteye.signals import sample_instance
    rec = Recognizer.load(C.ARTIFACTS / "gaf_cnn.pt")
    rng = np.random.default_rng(1)
    cam, k = gradcam(rec, event_waveform(sample_instance("soudage", rng), 0.9, rng))
    assert cam.shape == (C.GAF_SIZE, C.GAF_SIZE) and 0 <= cam.min() and cam.max() <= 1.0 + 1e-6 and 0 <= k < 7


def test_mcp_server_exposes_tools():
    pytest.importorskip("mcp")
    import anyio
    from agent.mcp_server import mcp
    names = {t.name for t in anyio.run(mcp.list_tools)}
    assert {"anomalies", "sante", "voltEye_grid", "recherche_documentation", "requete_sql"} <= names


def _db():
    from api import db
    try:
        db.wait_for_db(timeout=3)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db(), reason="base TimescaleDB indisponible")
def test_offline_answers_quote_tool_values(monkeypatch):
    monkeypatch.setenv("VOLTEYE_LLM", "off")
    a = assistant.answer("Combien la fuite d'air de février nous a-t-elle coûté, et que faut-il faire ?")
    assert correct(a["reponse"], tools.anomalies("compresseur", "février")["cout_total_TND"])
    g = assistant.answer("Combien de mégawatts VoltEye Grid efface-t-il pendant la pointe d'été ?")
    assert correct(g["reponse"], tools.voltEye_grid()["effacement_MW"])
    d = assistant.answer("Comment réparer une fuite d'air comprimé ?")
    assert d["sources"] and "ultrasons" in d["reponse"]
