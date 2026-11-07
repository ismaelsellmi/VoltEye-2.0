"""Tests de l'API (exigent une base TimescaleDB joignable : docker compose up -d db)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
pytest.importorskip("fastapi")
pytest.importorskip("psycopg")
pytest.importorskip("sqlalchemy")

from api import db  # noqa: E402


def _db_available():
    try:
        db.wait_for_db(timeout=3)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="base TimescaleDB indisponible")


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("AUTO_SEED", "1")
    from fastapi.testclient import TestClient

    from api.main import app
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", ["/api/sites", "/api/machines", "/api/kpis", "/api/consommation?pas=jour",
                                  "/api/anomalies?alertes_seules=true", "/api/sante", "/api/prevision", "/api/planning",
                                  "/api/grid", "/api/evaluation", "/api/direct", "/api/evenements", "/api/sante-service"])
def test_endpoints_answer(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text


def test_reference_data(client):
    assert len(client.get("/api/machines").json()) == 7
    sites = client.get("/api/sites").json()
    assert {s["kind"] for s in sites} == {"usine", "zone"} and len(sites) == 12
    k = client.get("/api/kpis").json()
    assert k["energie_kWh"] > 0 and 0 < k["modeles"]["anomalies_f1_test"] <= 1


def test_grid_day(client):
    days = client.get("/api/grid").json()["jours"]
    d = client.get(f"/api/grid/{days[0]}").json()
    assert d["voltEye_grid"]["pointe_MW"] <= d["pratique_actuelle"]["pointe_MW"]


def test_live_optimisation(client):
    base = [20.0] * 6 + [80.0] * 16 + [20.0] * 2
    r = client.post("/api/optimiser", json={"base_kw": base, "mois": 7}).json()
    assert r["voltEye"]["facture_TND"] <= r["operateur_averti"]["facture_TND"] + 1e-6
    assert r["voltEye"]["facture_TND"] <= r["pratique_actuelle"]["facture_TND"] + 1e-6


def test_bad_requests(client):
    assert client.get("/api/sites/../kpis?site=inconnu").status_code in (404, 422)
    assert client.get("/api/kpis?site=inconnu").status_code == 404
    assert client.post("/api/optimiser", json={"base_kw": [1, 2, 3]}).status_code == 422


def test_read_only_sql_guard():
    with pytest.raises(ValueError):
        db.safe_select("DELETE FROM site")
    with pytest.raises(ValueError):
        db.safe_select("SELECT 1; DROP TABLE site")
    assert db.safe_select("SELECT count(*) AS n FROM site")[0]["n"] == 12
