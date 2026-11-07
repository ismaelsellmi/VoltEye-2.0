"""Exécute toute la chaîne VoltEye : données, entraînement, évaluation, figures.

Usage : python -m volteye.pipeline   (environ 1 minute sur un portable)
"""
import json
import sys
import time

from . import anomaly, config as C, forecasting, grid, hipe, history, optimization, recognition, solar, stream


def main():
    for s in (sys.stdout, sys.stderr):           # journaux lisibles dans toutes les consoles
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    t0 = time.time()
    C.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    rec, _ = recognition.run()
    stream.run(rec)
    print("Historique : simulation d'un an de données horaires…")
    hist = history.simulate()
    hist.to_parquet(C.ARTIFACTS / "history.parquet")
    fc, _ = forecasting.run(hist)
    anomaly.run(hist)
    opt = optimization.run(fc)
    solar.run(hist)                # solaire en toiture : charge nette et pointe d'été
    am = json.loads((C.ARTIFACTS / "anomaly_metrics.json").read_text(encoding="utf-8"))
    grid.run(opt_summary=opt, anomaly_metrics=am)    # VoltEye Grid : 10 zones, pointe d'été
    hipe.run()                     # validation sur données réelles (si l'archive HIPE est présente)
    try:
        from . import figures
        figures.main()
    except ImportError:
        pass
    print(f"Terminé en {time.time() - t0:.0f} s. Résultats dans {C.ARTIFACTS}")


if __name__ == "__main__":
    main()
