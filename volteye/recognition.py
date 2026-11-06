"""Reconnaissance des charges : quelle machine vient de démarrer ou de s'arrêter ?

Entrée : la forme d'onde « différence » d'un événement (courant après moins
courant avant), mesurée au point unique de l'atelier.
Quatre approches comparées sur les mêmes données :
  A. baseline « mesures classiques » : forêt aléatoire sur P, Q, S, FP, I, THD ;
  B. baseline « spectre FFT »        : forêt aléatoire sur les harmoniques + P, FP ;
  C. CNN GAF                         : ondelettes + harmoniques -> GAF RGB -> CNN,
                                       avec P, Q, FP, THD injectés dans la tête du réseau ;
  D. VoltEye (modèle retenu)         : fusion des probabilités de C et B.
"""
import json
import time

import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from . import config as C
from .gaf import rgb_image
from .signals import CLASSES, MACHINE_TYPES, current, harmonic_spectrum, measurements, sample_instance


# --- Données d'événements ------------------------------------------------------

def event_waveform(inst, load, rng, noise=1.0):
    """Différence de courant d'un événement, avec les imperfections d'une mesure réelle."""
    i = current(inst, load)
    other = sample_instance(CLASSES[rng.integers(len(CLASSES))], rng)
    i = i + rng.uniform(0.02, 0.12) * noise * current(other, rng.uniform(0.3, 1.0))   # soustraction imparfaite
    i = i + rng.normal(0, 0.02 * noise * np.abs(i).max(), size=i.shape)               # bruit capteur
    return np.roll(i, int(rng.integers(-1, 2)))                                         # gigue de synchronisation


def make_dataset(n_per_class, rng, noise=1.0):
    waves, labels = [], []
    for k, m in enumerate(CLASSES):
        for _ in range(n_per_class):
            waves.append(event_waveform(sample_instance(m, rng), rng.uniform(0.35, 1.0), rng, noise))
            labels.append(k)
    return np.array(waves), np.array(labels)


def scalar_features(i):
    m = measurements(i)
    return [m["P_kW"], m["Q_kvar"], m["S_kVA"], m["PF"], m["I_rms_A"], m["THD"]]


def fft_features(i):
    h = harmonic_spectrum(i)
    m = measurements(i)
    return list(h[1:15] / max(h[0], 1e-9)) + [m["P_kW"], m["PF"]]


def cnn_scalars(i):
    m = measurements(i)
    return [np.log1p(max(m["P_kW"], 0)), np.log1p(m["Q_kvar"]), m["PF"], m["THD"]]


# --- Modèle CNN ----------------------------------------------------------------

class GafCNN(nn.Module):
    def __init__(self, n_classes=len(CLASSES), n_scalars=4):
        super().__init__()

        def block(cin, cout):
            return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(), nn.MaxPool2d(2))

        self.features = nn.Sequential(block(3, 16), block(16, 32), block(32, 64), nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.head = nn.Sequential(nn.Linear(64 + n_scalars, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, n_classes))

    def forward(self, img, scal):
        return self.head(torch.cat([self.features(img), scal], dim=1))


class Recognizer:
    """Modèle VoltEye prêt à l'emploi : CNN GAF, fusionné (moyenne des probabilités)
    avec la forêt aléatoire sur le spectre FFT quand `rf` est fourni."""

    def __init__(self, model, mu, sd, rf=None):
        self.model, self.mu, self.sd, self.rf = model.eval(), mu, sd, rf

    def _tensors(self, waves):
        imgs = torch.tensor(np.stack([rgb_image(w) for w in waves]))
        sc = (np.array([cnn_scalars(w) for w in waves]) - self.mu) / self.sd
        return imgs, torch.tensor(sc, dtype=torch.float32)

    def predict_proba_cnn(self, waves):
        with torch.no_grad():
            return torch.softmax(self.model(*self._tensors(waves)), dim=1).numpy()

    def predict_proba(self, waves):
        p = self.predict_proba_cnn(waves)
        if self.rf is not None:
            p = 0.5 * p + 0.5 * self.rf.predict_proba(np.array([fft_features(w) for w in waves]))
        return p

    def predict(self, waves):
        return self.predict_proba(waves).argmax(1)

    def save(self, path):
        torch.save({"state": self.model.state_dict(), "mu": self.mu, "sd": self.sd, "rf": self.rf}, path)

    @classmethod
    def load(cls, path):
        ck = torch.load(path, weights_only=False)
        model = GafCNN()
        model.load_state_dict(ck["state"])
        return cls(model, ck["mu"], ck["sd"], ck.get("rf"))


def train_cnn(w_tr, y_tr, w_va, y_va, epochs=25, seed=C.SEED, log=print):
    torch.manual_seed(seed)
    sc_tr = np.array([cnn_scalars(w) for w in w_tr])
    mu, sd = sc_tr.mean(0), sc_tr.std(0) + 1e-9
    rec = Recognizer(GafCNN(), mu, sd)
    x_img, x_sc = rec._tensors(w_tr)
    v_img, v_sc = rec._tensors(w_va)
    y = torch.tensor(y_tr)
    model = rec.model
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    best, best_state, history = 0.0, None, []
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(y))
        for b in range(0, len(y), 128):
            idx = perm[b:b + 128]
            opt.zero_grad()
            loss = nn.functional.cross_entropy(model(x_img[idx], x_sc[idx]), y[idx])
            loss.backward()
            opt.step()
        sched.step()
        model.eval()
        with torch.no_grad():
            acc = (model(v_img, v_sc).argmax(1).numpy() == y_va).mean()
        history.append({"epoch": ep + 1, "val_accuracy": float(acc), "loss": float(loss)})
        if acc >= best:
            best, best_state = acc, {k: v.clone() for k, v in model.state_dict().items()}
        log(f"  époque {ep + 1:02d}  perte={loss:.3f}  exactitude validation={acc:.3f}")
    model.load_state_dict(best_state)
    rec.model = model.eval()
    return rec, history


# --- Entraînement et évaluation comparée ------------------------------------------

def _scores(y, pred, seconds, n):
    return {"accuracy": float(accuracy_score(y, pred)), "f1_macro": float(f1_score(y, pred, average="macro")),
            "ms_par_evenement": 1000 * seconds / n}


def run(out_dir=C.ARTIFACTS, log=print):
    rng = np.random.default_rng(C.SEED)
    log("Reconnaissance : génération des événements simulés…")
    w_tr, y_tr = make_dataset(700, rng)
    w_va, y_va = make_dataset(150, rng)
    w_te, y_te = make_dataset(300, rng)
    w_hard, y_hard = make_dataset(150, rng, noise=3.0)   # test de robustesse : bruit x3

    results, preds = {}, {}
    for name, feat in [("A - Mesures classiques + forêt aléatoire", scalar_features),
                       ("B - Spectre FFT + forêt aléatoire", fft_features)]:
        rf = RandomForestClassifier(300, random_state=C.SEED, n_jobs=-1)
        rf.fit(np.array([feat(w) for w in w_tr]), y_tr)
        t = time.perf_counter()
        p = rf.predict(np.array([feat(w) for w in w_te]))
        results[name] = _scores(y_te, p, time.perf_counter() - t, len(y_te))
        results[name]["accuracy_bruit_x3"] = float(accuracy_score(y_hard, rf.predict(np.array([feat(w) for w in w_hard]))))
        preds[name] = p
        log(f"  {name}: exactitude={results[name]['accuracy']:.3f}")
    rf_fft = rf

    log("Reconnaissance : entraînement du CNN GAF…")
    rec, history = train_cnn(w_tr, y_tr, w_va, y_va, log=log)
    for name, fused in [("C - Ondelettes + GAF + CNN", None), ("D - VoltEye : fusion CNN GAF + spectre FFT", rf_fft)]:
        rec.rf = fused
        t = time.perf_counter()
        p = rec.predict(w_te)
        results[name] = _scores(y_te, p, time.perf_counter() - t, len(y_te))
        results[name]["accuracy_bruit_x3"] = float(accuracy_score(y_hard, rec.predict(w_hard)))
        preds[name] = p
        log(f"  {name}: exactitude={results[name]['accuracy']:.3f}  (bruit x3 : {results[name]['accuracy_bruit_x3']:.3f})")

    out_dir.mkdir(parents=True, exist_ok=True)
    rec.save(out_dir / "gaf_cnn.pt")
    payload = {
        "classes": CLASSES,
        "labels": [MACHINE_TYPES[c].label for c in CLASSES],
        "n_train": int(len(y_tr)), "n_val": int(len(y_va)), "n_test": int(len(y_te)),
        "models": results,
        "confusion_volteye": confusion_matrix(y_te, preds[name]).tolist(),
        "confusion_baseline_A": confusion_matrix(y_te, preds["A - Mesures classiques + forêt aléatoire"]).tolist(),
        "training_history": history,
        "per_class_f1_volteye": dict(zip(CLASSES, f1_score(y_te, preds[name], average=None).round(4).tolist())),
    }
    (out_dir / "recognition_metrics.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return rec, payload
