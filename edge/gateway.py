"""Passerelle edge VoltEye (Raspberry Pi simulé) : traitement sur place, publication MQTT.

Mode « simulation » : atelier de 7 machines mesuré par le capteur unique à 1 Hz ; la passerelle détecte
les démarrages et arrêts en continu, isole la forme d'onde de l'événement et la reconnaît avec le modèle
GAF-CNN fusionné, puis tient à jour la puissance estimée de chaque machine.
Mode « hipe » : rejeu d'une journée réelle de l'usine HIPE (KIT) au pas de 5 s, avec détection d'événements.

Seuls les indicateurs (1 message par seconde) et les événements (avec un extrait de 40 ms) quittent le
site, jamais le signal brut.
Sujets : volteye/<site>/mesures et volteye/<site>/evenements.

Usage : python -m edge.gateway   (variables : MQTT_HOST, MQTT_PORT, SITE, MODE, SPEED)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np

from volteye import config as C

SITE = os.environ.get("SITE", "usine-ref")
MODE = os.environ.get("MODE", "simulation")
SPEED = float(os.environ.get("SPEED", "1"))
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883" if "MQTT_HOST" in os.environ else "11883"))


class StreamingDetector:
    """Règle de stream.detect_events appliquée au fil de l'eau : écart des médianes après/avant,
    maximum local sur ±half échantillons, au moins half échantillons entre deux événements.
    Un événement est confirmé 2*half échantillons après son instant."""

    def __init__(self, threshold=0.8, half=3):
        self.threshold, self.half = threshold, half
        self.p = []
        self.last = -10 ** 9

    def _delta(self, k):
        h = self.half
        return float(np.median(self.p[k + 1:k + 1 + h]) - np.median(self.p[k - h:k]))

    def push(self, value):
        """Ajoute une mesure ; renvoie (indice, delta) si un événement est confirmé, sinon None."""
        self.p.append(float(value))
        h, n = self.half, len(self.p) - 1
        c = n - 2 * h
        if c - h < h:
            return None
        deltas = [self._delta(k) for k in range(c - h, c + h + 1)]
        d = deltas[h]
        if abs(d) >= self.threshold and abs(d) == max(abs(x) for x in deltas) and c - self.last > h:
            self.last = c
            return c, d
        if len(self.p) > 10_000:                     # mémoire bornée
            drop = len(self.p) - 1_000
            self.p, self.last = self.p[drop:], self.last - drop
        return None


def _iso(t):
    return t.isoformat(timespec="seconds")


class SimulatedSite:
    def __init__(self, hours=4):
        from volteye import stream
        from volteye.explain import gradcam_list
        from volteye.recognition import Recognizer
        self.gradcam = gradcam_list
        self.stream = stream
        rng = np.random.default_rng(C.SEED + 21)
        self.rng = rng
        self.site = stream.build_site(rng)
        self.load = stream.simulate(self.site, hours * 3600, rng)
        self.recognizer = Recognizer.load(C.ARTIFACTS / "gaf_cnn.pt")
        self.cache = {}
        self.det = StreamingDetector()
        self.est = {inst.mtype: 0.0 for inst in self.site}
        self.t = 0
        self.period = 1.0

    def _meas(self, k):
        key = tuple(self.load[k])
        if key not in self.cache:
            self.cache[key] = self.stream.measurements(self.stream.aggregate_waveform(self.site, self.load[k]))
        return self.cache[key]

    def step(self, now):
        k = self.t % len(self.load)
        m = dict(self._meas(k))
        p = m["P_kW"] + self.rng.normal(0, 0.15)
        events = []
        hit = self.det.push(p)
        if hit:
            c, d = hit
            back = len(self.det.p) - 1 - c
            kc = (self.t - back) % len(self.load)
            before = self.stream.aggregate_waveform(self.site, self.load[(kc - 2) % len(self.load)])
            after = self.stream.aggregate_waveform(self.site, self.load[(kc + 2) % len(self.load)])
            diff = after - before
            diff = diff + self.rng.normal(0, 0.02 * np.abs(diff).max() + 1e-6, size=diff.shape)
            wave = diff if d > 0 else -diff
            proba = self.recognizer.predict_proba([wave])[0]
            cam, _ = self.gradcam(self.recognizer, wave)
            classes = list(self.est)
            pred = classes[int(proba.argmax())]
            self.est[pred] = abs(d) if d > 0 else 0.0
            changed = np.flatnonzero(np.abs(self.load[(kc + 2) % len(self.load)] - self.load[(kc - 2) % len(self.load)]) > 1e-9)
            events.append({"time": _iso(now - timedelta(seconds=back)), "direction": "marche" if d > 0 else "arrêt",
                           "delta_kw": round(d, 3), "mtype": pred, "confiance": round(float(proba.max()), 4),
                           "proba": {c_: round(float(x), 4) for c_, x in zip(classes, proba)},
                           "verite": self.site[changed[0]].mtype if len(changed) else None,
                           "waveform": [round(float(x), 3) for x in wave], "gradcam": cam})
        mes = {"time": _iso(now), "p_kw": round(p, 3), "q_kvar": round(m["Q_kvar"], 3), "pf": round(m["PF"], 4),
               "thd": round(m["THD"], 4), "estime": {k_: round(v, 2) for k_, v in self.est.items()},
               "verite": {inst.mtype: round(inst.p_rated * self.load[k][j], 2) for j, inst in enumerate(self.site)}}
        self.t += 1
        return mes, events


class HipeReplay:
    """Journée réelle HIPE au pas de 5 s ; détection d'événements sur l'arrivée générale."""

    def __init__(self):
        import pandas as pd
        self.df = pd.read_parquet(C.ARTIFACTS / "hipe_replay.parquet").ffill().fillna(0)
        self.det = StreamingDetector(threshold=0.8, half=3)
        self.t = 0
        self.period = 5.0

    def step(self, now):
        r = self.df.iloc[self.t % len(self.df)]
        p = float(r["MainTerminal|P_kW"])
        events = []
        hit = self.det.push(p)
        if hit:
            c, d = hit
            back = 5 * (len(self.det.p) - 1 - c)
            events.append({"time": _iso(now - timedelta(seconds=back)), "direction": "marche" if d > 0 else "arrêt",
                           "delta_kw": round(d, 3), "mtype": None, "confiance": None, "proba": {}, "waveform": None})
        machines = {c.split("|")[0]: round(float(r[c]), 3) for c in self.df.columns
                    if c.endswith("|P_kW") and not c.startswith("MainTerminal")}
        mes = {"time": _iso(now), "p_kw": round(p, 3), "q_kvar": round(float(r["MainTerminal|Q_kvar"]), 3),
               "pf": round(float(r["MainTerminal|PF"]), 4), "thd": round(float(r["MainTerminal|THD"]) / 100, 4),
               "estime": {}, "verite": machines, "heure_source": str(self.df.index[self.t % len(self.df)])}
        self.t += 1
        return mes, events


def main():
    import paho.mqtt.client as mqtt
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    source = SimulatedSite() if MODE == "simulation" else HipeReplay()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"volteye-edge-{SITE}")
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()
    print(f"Passerelle {SITE} ({MODE}) → mqtt://{MQTT_HOST}:{MQTT_PORT}, vitesse x{SPEED}", flush=True)
    nxt = time.monotonic()
    clock = datetime.now(timezone.utc).replace(microsecond=0)      # horloge du flux (accélérée si SPEED > 1)
    while True:
        mes, events = source.step(clock)
        clock += timedelta(seconds=source.period)
        client.publish(f"volteye/{SITE}/mesures", json.dumps(mes))
        for e in events:
            client.publish(f"volteye/{SITE}/evenements", json.dumps(e))
            print(f"{e['time']}  {e['direction']:6s} {e['delta_kw']:+7.2f} kW  → {e['mtype']}", flush=True)
        nxt += source.period / SPEED
        time.sleep(max(0.0, nxt - time.monotonic()))


if __name__ == "__main__":
    main()
