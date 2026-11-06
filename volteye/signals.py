"""Catalogue des machines industrielles et génération des formes d'onde de courant.

Chaque type de machine possède une signature électrique : puissance, facteur de
puissance de déplacement et spectre harmonique (rangs impairs). Les ordres de
grandeur suivent les profils typiques de la littérature (charge résistive,
moteur asynchrone, redresseur 6 pulses de variateur, alimentation à découpage,
onduleur de soudage). Chaque instance tire ses paramètres autour de la signature
de sa classe, ce qui rend la reconnaissance non triviale.
"""
from dataclasses import dataclass, field

import numpy as np
import pywt

from . import config as C


@dataclass
class MachineType:
    key: str
    label: str
    p_range: tuple            # puissance nominale (kW)
    pf_range: tuple           # facteur de puissance de déplacement
    harmonics: dict           # rang -> (ratio moyen / fondamental, phase moyenne en rad)
    thd_load_sensitivity: float = 0.0   # hausse relative des harmoniques à faible charge
    color: str = "#888888"


MACHINE_TYPES = {
    m.key: m
    for m in [
        MachineType("four", "Four / étuve résistif", (15, 40), (0.98, 1.0),
                    {3: (0.015, 0.0), 5: (0.01, 0.0)}, 0.0, "#e4572e"),
        MachineType("compresseur", "Compresseur d'air (moteur asynchrone)", (11, 30), (0.78, 0.87),
                    {3: (0.04, 0.4), 5: (0.06, 2.6), 7: (0.03, 1.2)}, 0.2, "#4c8eda"),
        MachineType("cnc", "Machine CNC (variateur de vitesse)", (5, 25), (0.92, 0.97),
                    {5: (0.34, 3.0), 7: (0.22, 0.2), 11: (0.08, 2.9), 13: (0.05, 0.3)}, 0.6, "#29a36a"),
        MachineType("convoyeur", "Convoyeur (moteur direct)", (3, 11), (0.72, 0.84),
                    {3: (0.05, 0.6), 5: (0.04, 2.2), 7: (0.02, 1.0)}, 0.2, "#9b59b6"),
        MachineType("eclairage", "Éclairage LED (drivers électroniques)", (2, 8), (0.90, 0.96),
                    {3: (0.22, 3.1), 5: (0.11, 0.3), 7: (0.06, 2.8), 9: (0.04, 0.4)}, 0.3, "#f2c14e"),
        MachineType("soudage", "Poste de soudage (onduleur)", (5, 20), (0.66, 0.80),
                    {3: (0.48, 3.0), 5: (0.26, 0.1), 7: (0.14, 3.0), 9: (0.07, 0.2), 11: (0.04, 3.1)}, 0.3, "#d35400"),
        MachineType("cvc", "CVC / climatisation (compresseur inverter)", (8, 25), (0.93, 0.98),
                    {3: (0.05, 1.0), 5: (0.20, 2.7), 7: (0.11, 0.6), 11: (0.04, 2.5)}, 0.5, "#16a5a5"),
    ]
}
CLASSES = list(MACHINE_TYPES)


@dataclass
class MachineInstance:
    """Machine physique installée sur un site (paramètres fixés à l'installation)."""
    name: str
    mtype: str
    p_rated: float
    pf: float
    harmonics: dict = field(default_factory=dict)

    @property
    def spec(self) -> MachineType:
        return MACHINE_TYPES[self.mtype]


def sample_instance(mtype: str, rng: np.random.Generator, name: str | None = None) -> MachineInstance:
    spec = MACHINE_TYPES[mtype]
    harmonics = {
        h: (r * rng.uniform(0.6, 1.4), ph + rng.normal(0, 0.35))
        for h, (r, ph) in spec.harmonics.items()
    }
    return MachineInstance(
        name or spec.label,
        mtype,
        float(rng.uniform(*spec.p_range)),
        float(rng.uniform(*spec.pf_range)),
        harmonics,
    )


def time_axis(n_cycles: int = C.N_CYCLES) -> np.ndarray:
    return np.arange(n_cycles * C.SAMPLES_PER_CYCLE) / C.FS


def voltage(n_cycles: int = C.N_CYCLES) -> np.ndarray:
    """Tension phase-neutre légèrement déformée (5 % de rang 5 typique d'un réseau industriel)."""
    w = 2 * np.pi * C.F_GRID * time_axis(n_cycles)
    vp = np.sqrt(2) * C.V_PHASE
    return vp * np.sin(w) + 0.02 * vp * np.sin(5 * w + 0.3)


def current(inst: MachineInstance, load: float = 1.0, n_cycles: int = C.N_CYCLES) -> np.ndarray:
    """Courant de phase (A) absorbé par une machine à un taux de charge donné."""
    if load <= 0:
        return np.zeros(n_cycles * C.SAMPLES_PER_CYCLE)
    w = 2 * np.pi * C.F_GRID * time_axis(n_cycles)
    p_kw = inst.p_rated * load
    i1 = p_kw * 1000 / (3 * C.V_PHASE * inst.pf)            # efficace du fondamental, par phase
    i = np.sqrt(2) * i1 * np.sin(w - np.arccos(inst.pf))
    boost = 1 + inst.spec.thd_load_sensitivity * (1 - min(load, 1.0))
    for h, (ratio, phase) in inst.harmonics.items():
        i += np.sqrt(2) * i1 * ratio * boost * np.sin(h * w + phase)
    return i


# --- Mesures électriques (ce que calcule le capteur) ---------------------------

def harmonic_spectrum(i: np.ndarray, n_cycles: int = C.N_CYCLES) -> np.ndarray:
    """Amplitudes efficaces des rangs 1..N_HARMONICS."""
    spec = np.abs(np.fft.rfft(i)) * np.sqrt(2) / len(i)
    return spec[n_cycles: n_cycles * (C.N_HARMONICS + 1): n_cycles]


def measurements(i: np.ndarray, v: np.ndarray | None = None) -> dict:
    """P, Q, S, facteur de puissance, courant efficace et THD (triphasé équilibré)."""
    v = voltage() if v is None else v
    p = 3 * np.mean(v * i) / 1000
    i_rms = np.sqrt(np.mean(i ** 2))
    s = 3 * np.sqrt(np.mean(v ** 2)) * i_rms / 1000
    q = np.sqrt(max(s ** 2 - p ** 2, 0.0))
    h = harmonic_spectrum(i)
    thd = np.sqrt(np.sum(h[1:] ** 2)) / h[0] if h[0] > 1e-9 else 0.0
    return {"P_kW": p, "Q_kvar": q, "S_kVA": s, "PF": p / s if s > 1e-9 else 0.0,
            "I_rms_A": i_rms, "THD": thd}


# --- Séquences d'entrée du modèle (chaîne de la méthode publiée) ---------------

def _resample(x: np.ndarray, n: int) -> np.ndarray:
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def feature_sequences(i: np.ndarray) -> dict:
    """Les trois séquences du pipeline : approximation et détail (ondelette db4) et contenu harmonique."""
    c_a, c_d = pywt.dwt(i, "db4")
    h = harmonic_spectrum(i)
    harm = h / h[0] if h[0] > 1e-9 else h
    return {
        "approximation": _resample(c_a, C.GAF_SIZE),
        "detail": _resample(c_d, C.GAF_SIZE),
        "harmoniques": _resample(harm, C.GAF_SIZE),
    }
