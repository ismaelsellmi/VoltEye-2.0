"""Gramian Angular Field (GAF) : transformer une séquence 1D en image 2D.

1. normalisation de la séquence dans [-1, 1] ;
2. passage en coordonnées polaires : phi = arccos(x) ;
3. GASF[i, j] = cos(phi_i + phi_j).
Les trois séquences (approximation, détail, harmoniques) donnent trois images
en niveaux de gris fusionnées dans les canaux R, V, B d'une image couleur.
"""
import numpy as np

from .signals import feature_sequences


def gasf(x: np.ndarray) -> np.ndarray:
    lo, hi = x.min(), x.max()
    x = np.zeros_like(x) if hi - lo < 1e-12 else 2 * (x - lo) / (hi - lo) - 1
    phi = np.arccos(np.clip(x, -1, 1))
    return np.cos(phi[:, None] + phi[None, :])


def polar(x: np.ndarray) -> tuple:
    """Coordonnées polaires utilisées par le GAF (angle, rayon) pour l'affichage."""
    lo, hi = x.min(), x.max()
    xn = np.zeros_like(x) if hi - lo < 1e-12 else 2 * (x - lo) / (hi - lo) - 1
    return np.arccos(np.clip(xn, -1, 1)), np.linspace(0, 1, len(x))


def rgb_image(i: np.ndarray) -> np.ndarray:
    """Image couleur (3, H, W) dans [-1, 1] à partir d'une forme d'onde de courant."""
    seq = feature_sequences(i)
    return np.stack([gasf(seq["approximation"]), gasf(seq["detail"]), gasf(seq["harmoniques"])]).astype(np.float32)


def to_display(img: np.ndarray) -> np.ndarray:
    """(3, H, W) dans [-1, 1] vers (H, W, 3) uint8 pour l'affichage."""
    return ((np.transpose(img, (1, 2, 0)) + 1) * 127.5).clip(0, 255).astype(np.uint8)
