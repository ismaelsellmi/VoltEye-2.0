"""Temps réel : abonnement MQTT aux passerelles, enregistrement en base et diffusion WebSocket."""
import asyncio
import json
import logging
import os

import paho.mqtt.client as mqtt
from sqlalchemy import text

from . import db

log = logging.getLogger("volteye.live")
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883" if "MQTT_HOST" in os.environ else "11883"))
TOPIC = "volteye/+/+"


class Hub:
    """Relie le fil MQTT (paho) à la boucle asyncio de FastAPI."""

    def __init__(self):
        self.clients = set()
        self.loop = None
        self.client = None
        self.meters = {}
        self.received = 0

    # --- WebSocket ----------------------------------------------------------------
    async def connect(self, ws):
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws):
        self.clients.discard(ws)

    async def broadcast(self, msg):
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except Exception:
                self.clients.discard(ws)

    # --- MQTT ---------------------------------------------------------------------
    def start(self, loop):
        self.loop = loop
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="volteye-api")
        self.client.on_connect = lambda c, u, f, rc, p: c.subscribe(TOPIC, qos=0)
        self.client.on_message = self.on_message
        self.client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
        self.client.loop_start()                     # reconnexion automatique si le broker n'est pas prêt

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    @property
    def connected(self):
        return bool(self.client and self.client.is_connected())

    def meter_id(self, site):
        if site not in self.meters:
            self.meters[site] = db.scalar("SELECT m.id FROM meter m JOIN site s ON s.id = m.site_id WHERE s.code = :c "
                                          "ORDER BY m.id LIMIT 1", c=site)
        return self.meters[site]

    def on_message(self, client, userdata, message):
        try:
            _, site, kind = message.topic.split("/")
            p = json.loads(message.payload)
            meter = self.meter_id(site)
            if meter is None:
                return
            with db.engine().begin() as cx:
                if kind == "mesures":
                    cx.execute(text("INSERT INTO measurement (time, meter_id, p_kw, q_kvar, pf, thd, estimated) "
                                    "VALUES (:time, :m, :p, :q, :pf, :thd, :est)"),
                               {"time": p["time"], "m": meter, "p": p.get("p_kw"), "q": p.get("q_kvar"), "pf": p.get("pf"),
                                "thd": p.get("thd"), "est": json.dumps(p.get("estime") or {})})
                elif kind == "evenements":
                    cx.execute(text("INSERT INTO event (time, meter_id, direction, delta_kw, mtype, confidence, proba, waveform) "
                                    "VALUES (:time, :m, :d, :dk, :mt, :c, :pr, :w)"),
                               {"time": p["time"], "m": meter, "d": p.get("direction"), "dk": p.get("delta_kw"),
                                "mt": p.get("mtype"), "c": p.get("confiance"), "pr": json.dumps(p.get("proba") or {}),
                                "w": p.get("waveform")})
                else:
                    return
            self.received += 1
            msg = {"type": "mesure" if kind == "mesures" else "evenement", "site": site, **p}
            if self.loop and self.clients:
                asyncio.run_coroutine_threadsafe(self.broadcast(msg), self.loop)
        except Exception:                            # un message invalide ne doit pas arrêter l'ingestion
            log.exception("message MQTT ignoré")


hub = Hub()
