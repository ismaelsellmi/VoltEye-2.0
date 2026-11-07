"""Télécharge le sous-ensemble d'une semaine du jeu de données HIPE (KIT, licence CC BY 4.0).

HIPE : High-resolution Industrial Production Energy, usine d'électronique de puissance du KIT
(Karlsruhe). 10 machines et l'arrivée générale, une mesure toutes les 5 s.
Archive : 109 Mo compressés. Elle est lue directement dans le zip, sans extraction.

Usage : python scripts/telecharger_hipe.py
"""
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "raw" / "hipe"
NAME = "hipe_cleaned_v1.0.1_geq_2017-10-23_lt_2017-10-30.zip"
URL = f"https://bwsyncandshare.kit.edu/s/JacGftzBH85dgGK/download?path=%2F&files={NAME}"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / NAME
    if target.exists() and zipfile.is_zipfile(target):
        print(f"Déjà présent : {target}")
        return target
    tmp = target.with_suffix(".part")
    print(f"Téléchargement de {NAME} (≈ 109 Mo)…")
    with urllib.request.urlopen(URL, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e6:6.1f} / {total / 1e6:.1f} Mo", end="", flush=True)
    print()
    if not zipfile.is_zipfile(tmp):
        tmp.unlink()
        sys.exit("Archive invalide : téléchargement à relancer.")
    tmp.replace(target)
    with zipfile.ZipFile(target) as z:
        print(f"OK : {len(z.namelist())} fichiers dans {target}")
    return target


if __name__ == "__main__":
    main()
