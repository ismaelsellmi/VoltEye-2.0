"""Figures du rapport technique (docs/figures/*.png), générées à partir des artefacts."""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C
from .gaf import gasf, rgb_image, to_display
from .signals import CLASSES, MACHINE_TYPES, current, feature_sequences, harmonic_spectrum, sample_instance, time_axis

A = C.ARTIFACTS
plt.rcParams.update({"figure.dpi": 150, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def _load(name):
    return json.loads((A / name).read_text(encoding="utf-8"))


def signatures():
    rng = np.random.default_rng(7)
    fig, ax = plt.subplots(len(CLASSES), 2, figsize=(8, 10), gridspec_kw={"width_ratios": [2, 1]})
    t = time_axis() * 1000
    for k, m in enumerate(CLASSES):
        inst = sample_instance(m, rng)
        inst.harmonics = {h: (r, ph) for h, (r, ph) in MACHINE_TYPES[m].harmonics.items()}
        i = current(inst, 0.8)
        ax[k, 0].plot(t, i, color=MACHINE_TYPES[m].color, lw=1.4)
        ax[k, 0].set_ylabel("A")
        ax[k, 0].set_title(MACHINE_TYPES[m].label, loc="left", fontsize=8)
        h = harmonic_spectrum(i)[:15]
        ax[k, 1].bar(np.arange(1, 16), h / h[0], color=MACHINE_TYPES[m].color)
        ax[k, 1].set_ylim(0, 1.05)
    ax[-1, 0].set_xlabel("temps (ms)")
    ax[-1, 1].set_xlabel("rang harmonique")
    fig.suptitle("Signatures électriques des 7 types de machines (courant et spectre harmonique)")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig_signatures.png")
    plt.close(fig)


def gaf_pipeline():
    rng = np.random.default_rng(3)
    inst = sample_instance("cnc", rng)
    i = current(inst, 0.8)
    seq = feature_sequences(i)
    fig, ax = plt.subplots(2, 4, figsize=(10, 5))
    for k, (name, s) in enumerate(seq.items()):
        ax[0, k].plot(s, color="#333")
        ax[0, k].set_title(f"Séquence : {name}", fontsize=8)
        ax[1, k].imshow(gasf(s), cmap="gray")
        ax[1, k].set_title(f"GAF {name}", fontsize=8)
        ax[1, k].axis("off")
    ax[0, 3].plot(time_axis() * 1000, i, color=MACHINE_TYPES["cnc"].color)
    ax[0, 3].set_title("Courant mesuré (CNC)", fontsize=8)
    ax[1, 3].imshow(to_display(rgb_image(i)))
    ax[1, 3].set_title("Image couleur fusionnée (RVB)", fontsize=8)
    ax[1, 3].axis("off")
    fig.suptitle("Du signal à l'image : ondelettes, harmoniques et Gramian Angular Field")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig_gaf_pipeline.png")
    plt.close(fig)


def recognition():
    r = _load("recognition_metrics.json")
    names = list(r["models"])
    acc = [r["models"][n]["accuracy"] for n in names]
    noisy = [r["models"][n]["accuracy_bruit_x3"] for n in names]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    x = np.arange(len(names))
    ax[0].bar(x - 0.2, acc, 0.4, label="test standard", color="#2a6fdb")
    ax[0].bar(x + 0.2, noisy, 0.4, label="test bruit x3", color="#9dbcf0")
    ax[0].set_xticks(x, [n.split(" - ")[0] for n in names])
    ax[0].set_ylim(0.6, 1.0)
    ax[0].set_ylabel("exactitude")
    ax[0].legend()
    for k, (a, b) in enumerate(zip(acc, noisy)):
        ax[0].text(k - 0.2, a + 0.005, f"{a:.3f}", ha="center", fontsize=7)
        ax[0].text(k + 0.2, b + 0.005, f"{b:.3f}", ha="center", fontsize=7)
    ax[0].set_title("Reconnaissance des machines : comparaison des approches")
    cm = np.array(r["confusion_volteye"])
    ax[1].imshow(cm / cm.sum(1, keepdims=True), cmap="Blues")
    ax[1].set_xticks(range(len(CLASSES)), CLASSES, rotation=45, ha="right")
    ax[1].set_yticks(range(len(CLASSES)), CLASSES)
    for a in range(len(CLASSES)):
        for b in range(len(CLASSES)):
            ax[1].text(b, a, cm[a, b], ha="center", va="center", fontsize=7,
                       color="white" if cm[a, b] > cm.max() / 2 else "black")
    ax[1].set_xlabel("prédit")
    ax[1].set_ylabel("réel")
    ax[1].set_title("Matrice de confusion VoltEye (D)")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig_recognition.png")
    plt.close(fig)


def stream():
    df = pd.read_parquet(A / "stream.parquet").iloc[:3600]
    fig, ax = plt.subplots(2, 1, figsize=(10, 5.5), sharex=True)
    ax[0].plot(df["time"], df["P_kW"], color="#222", lw=0.8)
    ax[0].set_ylabel("kW")
    ax[0].set_title("Signal unique mesuré au point de raccordement (1 mesure/s)")
    bottom = np.zeros(len(df))
    for m in CLASSES:
        ax[1].fill_between(df["time"], bottom, bottom + df[f"estime_{m}_kW"], color=MACHINE_TYPES[m].color,
                           label=m, step="post", alpha=0.85)
        bottom = bottom + df[f"estime_{m}_kW"].to_numpy()
    ax[1].set_ylabel("kW")
    ax[1].set_title("Consommation par machine reconstituée par VoltEye")
    ax[1].legend(ncol=7, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig_stream.png")
    plt.close(fig)


def forecast():
    fc = pd.read_parquet(A / "forecast_test.parquet").iloc[:24 * 14]
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(fc.index, fc["reel"], color="#222", lw=1.2, label="réel")
    ax.plot(fc.index, fc["prevision"], color="#2a6fdb", lw=1.2, label="prévision VoltEye (J+1)")
    ax.plot(fc.index, fc["baseline_semaine"], color="#e4572e", lw=0.8, ls="--", label="baseline semaine précédente")
    ax.set_ylabel("kWh / heure")
    ax.legend(fontsize=7)
    ax.set_title("Prévision horaire de la consommation à J+1 (2 semaines de la période de test)")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig_forecast.png")
    plt.close(fig)


def anomalies():
    d = pd.read_parquet(A / "anomalies_daily.parquet")
    h = pd.read_parquet(A / "health_daily.parquet")
    fig, ax = plt.subplots(2, 1, figsize=(10, 6))
    c = d[d["machine"] == "compresseur"]
    ax[0].plot(c.index, c["energie_kWh"], color="#4c8eda", lw=1, label="énergie journalière")
    ax[0].plot(c.index, c["attendu_kWh"], color="#999", lw=1, label="attendue (modèle)")
    lab = c["verite"] == "fuite_air"
    ax[0].fill_between(c.index, 0, c["energie_kWh"].max(), where=lab, color="#f2c14e", alpha=0.3, label="fuite réelle")
    al = c[c["alerte"]]
    ax[0].scatter(al.index, al["energie_kWh"], color="#d62728", s=14, zorder=3, label="alerte VoltEye")
    ax[0].set_ylabel("kWh / jour")
    ax[0].legend(fontsize=7, ncol=4)
    ax[0].set_title("Détection des fuites d'air comprimé (compresseur)")
    v = h[h["machine"] == "convoyeur"]
    ax[1].plot(v.index, v["sante"], color="#9b59b6", lw=1.4, label="score de santé")
    ax[1].axvline(pd.Timestamp("2026-05-18"), color="#d62728", ls="--", label="panne réelle")
    first = v[v["alerte"]].index.min()
    ax[1].axvline(first, color="#f39c12", ls="--", label="première alerte VoltEye")
    ax[1].set_ylabel("santé (/100)")
    ax[1].set_xlim(pd.Timestamp("2026-02-15"), pd.Timestamp("2026-07-01"))
    ax[1].legend(fontsize=7)
    ax[1].set_title("Maintenance prédictive : dérive harmonique (THD) du moteur de convoyeur")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig_anomalies.png")
    plt.close(fig)


def optimization():
    o = _load("optimization.json")
    day = max(o["jours"], key=lambda d: d["facture_ref_TND"] - d["facture_opt_TND"])
    from .optimization import schedule_profile
    base = np.array(day["base"])
    fig, ax = plt.subplots(figsize=(10, 3.8))
    hrs = np.arange(24)
    ax.step(hrs, base + schedule_profile(day["ref"]), where="post", color="#e4572e", label="planning actuel")
    ax.step(hrs, base + schedule_profile(day["opt"]), where="post", color="#29a36a", label="planning optimisé VoltEye")
    ax.step(hrs, base, where="post", color="#999", ls=":", label="charge de base")
    ax2 = ax.twinx()
    ax2.step(hrs, day["prix"], where="post", color="#555", alpha=0.4)
    ax2.set_ylabel("tarif (TND/kWh)")
    ax.set_xlabel("heure")
    ax.set_ylabel("kW")
    ax.legend(fontsize=7, loc="upper left")
    ax.set_title(f"Optimisation du planning selon le tarif horaire - {day['jour']}")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig_optimization.png")
    plt.close(fig)


def main():
    C.FIGURES.mkdir(parents=True, exist_ok=True)
    for f in (signatures, gaf_pipeline, recognition, stream, forecast, anomalies, optimization):
        f()
    print(f"Figures enregistrées dans {C.FIGURES}")


if __name__ == "__main__":
    main()
