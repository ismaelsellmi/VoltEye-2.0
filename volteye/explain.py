"""Explicabilité de la reconnaissance : Grad-CAM sur les images GAF.

Grad-CAM (Selvaraju et al., 2017) pondère les cartes d'activation du dernier bloc convolutif par le
gradient de la classe prédite : la carte obtenue montre quelles zones de l'image GAF ont fait pencher la
décision du CNN. Les lignes et colonnes de l'image correspondent à des instants (ou des rangs
harmoniques) : une zone chaude indique les paires d'instants qui portent la signature de la machine.
"""
import numpy as np
import torch
import torch.nn.functional as F

from volteye.config import GAF_SIZE


def gradcam(recognizer, wave):
    """Carte Grad-CAM (GAF_SIZE x GAF_SIZE, valeurs 0..1) pour la classe prédite par le CNN, et cette classe."""
    model = recognizer.model.eval()
    img, sc = recognizer._tensors([wave])
    target_layer = model.features[2][2]            # ReLU du 3e bloc convolutif (8 x 8)
    store = {}

    def keep(_, __, out):
        out.retain_grad()
        store["act"] = out

    handle = target_layer.register_forward_hook(keep)
    try:
        logits = model(img, sc)
        k = int(logits.argmax(1))
        model.zero_grad()
        logits[0, k].backward()
    finally:
        handle.remove()
    act, grad = store["act"], store["act"].grad
    weights = grad.mean(dim=(2, 3), keepdim=True)
    cam = F.relu((weights * act).sum(dim=1, keepdim=True))
    cam = F.interpolate(cam, size=(GAF_SIZE, GAF_SIZE), mode="bilinear", align_corners=False)[0, 0].detach().numpy()
    if cam.max() > 1e-12:
        cam = cam / cam.max()
    return cam.astype(np.float32), k


def gradcam_list(recognizer, wave, digits=2):
    cam, k = gradcam(recognizer, wave)
    return np.round(cam, digits).tolist(), k


if __name__ == "__main__":
    from volteye import config as C
    from volteye.recognition import Recognizer, event_waveform
    from volteye.signals import CLASSES, sample_instance

    rec = Recognizer.load(C.ARTIFACTS / "gaf_cnn.pt")
    rng = np.random.default_rng(0)
    for m in CLASSES:
        cam, k = gradcam(rec, event_waveform(sample_instance(m, rng), 0.8, rng))
        print(f"{m:12s} -> {CLASSES[k]:12s}  zone chaude : {int((cam > 0.5).sum())} pixels sur {cam.size}")
