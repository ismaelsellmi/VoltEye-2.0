"""Vue « ville intelligente » : déploiement de VoltEye sur plusieurs sites industriels.

Les sites sont fictifs, placés dans des zones industrielles tunisiennes réelles.
Leurs indicateurs sont extrapolés à partir des résultats du site de référence,
avec un facteur d'échelle et un profil de gaspillage propres à chaque site
(données simulées pour illustrer la vision à l'échelle de la ville).
"""
import json

import numpy as np

from . import config as C

ZONES = [
    ("Zone industrielle Ben Arous", 36.745, 10.235, "Mécanique"),
    ("ZI Mghira", 36.683, 10.152, "Plasturgie"),
    ("ZI Charguia", 36.842, 10.203, "Agroalimentaire"),
    ("ZI Bizerte - Menzel Bourguiba", 37.155, 9.788, "Métallurgie"),
    ("ZI Sousse - Sidi Abdelhamid", 35.792, 10.636, "Textile"),
    ("ZI Monastir", 35.765, 10.808, "Textile"),
    ("ZI Sfax - Poudrière", 34.760, 10.745, "Agroalimentaire"),
    ("ZI Gabès", 33.905, 10.103, "Chimie"),
    ("ZI Nabeul - Grombalia", 36.598, 10.497, "Agroalimentaire"),
    ("ZI Béja", 36.735, 9.200, "Mécanique"),
]


def run(hist, anomaly_metrics, opt_summary, out_dir=C.ARTIFACTS, log=print):
    log("Vue ville : extrapolation à 10 sites industriels…")
    rng = np.random.default_rng(C.SEED + 4)
    base_mwh = hist["E_total"].sum() / 1000
    waste_share = anomaly_metrics["impact_anomalies_detectees"]["kWh_gaspilles_detectes"] / 1000 / base_mwh
    sites = []
    for name, lat, lon, sector in ZONES:
        scale = rng.uniform(0.6, 3.5)
        waste = waste_share * rng.uniform(0.6, 2.2)
        mwh = base_mwh * scale
        sites.append({
            "site": name, "lat": lat, "lon": lon, "secteur": sector,
            "consommation_MWh_an": mwh,
            "gaspillage_detecte_MWh_an": mwh * waste,
            "co2_t_an": mwh * C.EMISSION_FACTOR,
            "co2_evitable_t_an": mwh * waste * C.EMISSION_FACTOR,
            "gain_planification_TND_an": opt_summary["gain_annuel_estime_TND"] * scale,
            "alertes_actives": int(rng.integers(0, 6)),
            "sante_moyenne": float(rng.uniform(72, 98)),
        })
    (out_dir / "city_sites.json").write_text(json.dumps(sites, indent=2, ensure_ascii=False), encoding="utf-8")
    return sites
