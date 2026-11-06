"""Paramètres globaux de VoltEye.

Toutes les valeurs marquées « HYPOTHÈSE » sont des hypothèses de simulation
documentées dans docs/donnees.md : elles doivent être remplacées par les
valeurs officielles (STEG, ANME) lors d'un déploiement réel.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
FIGURES = ROOT / "docs" / "figures"

SEED = 42

# --- Électricité --------------------------------------------------------------
F_GRID = 50.0                 # Hz, réseau tunisien
SAMPLES_PER_CYCLE = 64        # échantillonnage 3,2 kHz
FS = F_GRID * SAMPLES_PER_CYCLE
N_CYCLES = 2                  # fenêtre d'analyse = 2 périodes (40 ms)
V_PHASE = 230.0               # V efficace phase-neutre (réseau 400 V triphasé)
N_HARMONICS = 31              # rangs analysés (Nyquist = rang 32)
GAF_SIZE = 32                 # taille des images GAF (32 x 32)

# --- Contexte tunisien (HYPOTHÈSES à confirmer avec STEG / ANME) ---------------
EMISSION_FACTOR = 0.50        # kg CO2 / kWh, facteur indicatif du réseau tunisien
# Tarif horaire indicatif pour un client industriel moyenne tension (TND/kWh)
TARIFFS = {"nuit": 0.210, "jour": 0.295, "pointe": 0.430}
PEAK_DEMAND_CHARGE = 0.60     # TND par kW de pointe journalière (pénalité de dépassement)


def tariff_period(hour: int, month: int) -> str:
    """Plage tarifaire (HYPOTHÈSE) : la pointe est le soir en hiver, en journée en été."""
    if hour >= 22 or hour < 6:
        return "nuit"
    if month in (6, 7, 8):
        return "pointe" if 9 <= hour < 14 else "jour"
    return "pointe" if 18 <= hour < 22 else "jour"


def tariff(hour: int, month: int) -> float:
    return TARIFFS[tariff_period(hour, month)]
