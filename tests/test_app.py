"""Test de fumée du tableau de bord Streamlit : chaque page s'affiche sans erreur."""
from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "streamlit_app.py"
PAGES = ["Vue d'ensemble", "Surveillance en direct", "Reconnaissance IA (GAF)", "Anomalies & maintenance",
         "Prévision & optimisation", "Vue ville", "Évaluation des modèles", "Architecture"]

pytestmark = pytest.mark.skipif(not (ROOT / "artifacts" / "optimization.json").exists(),
                                reason="artefacts absents : lancer python -m volteye.pipeline")


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]
