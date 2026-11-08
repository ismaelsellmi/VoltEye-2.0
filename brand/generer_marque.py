"""Génère les fichiers SVG de la marque VoltEye à partir de leur géométrie exacte.

Le symbole « œil-onde » : une période du courant alternatif dessine l'œil. L'alternance positive forme la
paupière du haut, l'alternance négative celle du bas, qui porte une ondulation discrète (la signature
harmonique, rang 5). L'axe du temps traverse l'œil ; la pupille jaune est le point de mesure unique.

Les courbes sont des arcs de sinusoïde convertis en courbes de Bézier cubiques (interpolation d'Hermite
avec les dérivées exactes). Le mot VOLTEYE est vectorisé depuis Barlow Condensed Bold (licence SIL OFL),
les fichiers ne dépendent donc d'aucune police installée.

Usage : python brand/generer_marque.py   (police lue dans web/node_modules : lancer npm install dans web/)
"""
import math
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent
FONT = ROOT.parent / "web" / "node_modules" / "@fontsource" / "barlow-condensed" / "files" / "barlow-condensed-latin-700-normal.woff"

INK, WHITE, BLUE, YELLOW, GREY = "#1B201E", "#FFFFFF", "#1D5FA6", "#F2C200", "#DCDED9"

# --- Géométrie du symbole (unités du symbole : 120 x 72, centre 60,36) -------------------------
X0, X1, CY = 14.0, 106.0, 36.0          # coins de l'œil et axe
AMP = 25.0                               # demi-hauteur de l'œil
RIPPLE = 1.2                             # amplitude de la signature harmonique (rang 5), discrète
AXIS = (4.0, 116.0)
LID, AXIS_W, PUPIL_R = 5.2, 3.2, 9.5


def _fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def hermite_path(f, df, t0, t1, n):
    """Courbe paramétrée (x(t), y(t)) convertie en n segments de Bézier cubiques (Hermite exact)."""
    pts = [t0 + (t1 - t0) * i / n for i in range(n + 1)]
    x, y = f(pts[0])
    d = [f"M{_fmt(x)} {_fmt(y)}"]
    for a, b in zip(pts, pts[1:]):
        h = b - a
        (xa, ya), (xb, yb) = f(a), f(b)
        (dxa, dya), (dxb, dyb) = df(a), df(b)
        d.append(f"C{_fmt(xa + dxa * h / 3)} {_fmt(ya + dya * h / 3)} {_fmt(xb - dxb * h / 3)} {_fmt(yb - dyb * h / 3)} "
                 f"{_fmt(xb)} {_fmt(yb)}")
    return " ".join(d)


def lids(amp=AMP, ripple=RIPPLE, x0=X0, x1=X1, cy=CY, k=1.0):
    """Paupières haute et basse ; k met à l'échelle (symbole dans un autre repère)."""
    w = x1 - x0

    def up(t):
        return (x0 + w * t) * k, (cy - amp * math.sin(math.pi * t)) * k

    def dup(t):
        return w * k, -amp * math.pi * math.cos(math.pi * t) * k

    def lo(t):
        s = math.sin(math.pi * t)
        return (x0 + w * t) * k, (cy + amp * s + ripple * math.sin(5 * math.pi * t) * s) * k

    def dlo(t):
        s, c = math.sin(math.pi * t), math.cos(math.pi * t)
        r5, c5 = math.sin(5 * math.pi * t), math.cos(5 * math.pi * t)
        dy = amp * math.pi * c + ripple * (5 * math.pi * c5 * s + r5 * math.pi * c)
        return w * k, dy * k

    return hermite_path(up, dup, 0, 1, 4), hermite_path(lo, dlo, 0, 1, 20 if ripple else 4)


def symbol_group(stroke, pupil, simple=False, dx=0.0, dy=0.0, scale=1.0):
    """Groupe SVG du symbole. simple=True : version des petites tailles (sans ondulation, traits épais)."""
    if simple:
        up, lo = lids(amp=28, ripple=0)
        lid, axis_w, r, axis = 10, 7, 15, (10, 110)
    else:
        up, lo = lids()
        lid, axis_w, r, axis = LID, AXIS_W, PUPIL_R, AXIS
    return (f'<g transform="translate({_fmt(dx)} {_fmt(dy)}) scale({_fmt(scale)})" fill="none" stroke="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<line x1="{_fmt(axis[0])}" y1="{_fmt(CY)}" x2="{_fmt(axis[1])}" y2="{_fmt(CY)}" stroke-width="{_fmt(axis_w)}"/>'
            f'<path d="{up}" stroke-width="{_fmt(lid)}"/><path d="{lo}" stroke-width="{_fmt(lid)}"/>'
            f'<circle cx="60" cy="{_fmt(CY)}" r="{_fmt(r)}" fill="{pupil}" stroke="none"/></g>')


# --- Mot VOLTEYE vectorisé -----------------------------------------------------------------------

def wordmark(text="VOLTEYE", cap=42.0, tracking=0.035):
    """Contours du mot ; renvoie (chemin SVG, largeur, hauteur de capitale) pour une hauteur de capitale donnée."""
    font = TTFont(str(FONT))
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    cap_units = getattr(font["OS/2"], "sCapHeight", 0) or font["head"].unitsPerEm * 0.7
    k = cap / cap_units
    upm = font["head"].unitsPerEm
    pen = SVGPathPen(gs)
    x = 0.0
    for i, ch in enumerate(text):
        g = cmap[ord(ch)]
        tp = TransformPen(pen, (k, 0, 0, -k, x, cap))        # repère SVG : y vers le bas, ligne de base à y = cap
        gs[g].draw(tp)
        x += gs[g].width * k + (tracking * upm * k if i < len(text) - 1 else 0)
    return pen.getCommands(), x, cap


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(w)} {_fmt(h)}" width="{_fmt(w)}" height="{_fmt(h)}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')


def build():
    out = {}
    # symbole seul : boîte 120 x 72 (zone de protection comprise dans les marges latérales)
    out["volteye-symbole.svg"] = svg(120, 72, symbol_group(INK, YELLOW), "VoltEye")
    out["volteye-symbole-inverse.svg"] = svg(120, 72, symbol_group(WHITE, YELLOW), "VoltEye")
    out["volteye-symbole-simple.svg"] = svg(120, 72, symbol_group(INK, YELLOW, simple=True), "VoltEye")

    # logo horizontal : hauteur de capitale = hauteur visible du symbole / 1,3, centrée sur l'axe
    cap = (2 * AMP + LID) / 1.3
    word, ww, _ = wordmark(cap=cap)
    gap = 2.4 * PUPIL_R
    sx1 = AXIS[1]
    wx = sx1 + gap
    W = wx + ww + 4
    for name, ink in (("volteye-logo-horizontal.svg", INK), ("volteye-logo-horizontal-inverse.svg", WHITE)):
        body = symbol_group(ink, YELLOW, dx=0) + f'<path d="{word}" fill="{ink}" transform="translate({_fmt(wx)} {_fmt(CY - cap / 2)})"/>'
        out[name] = svg(W, 72, body, "VoltEye")

    # logo empilé : symbole au-dessus du mot, centrés
    cap2 = 30.0
    word2, ww2, _ = wordmark(cap=cap2)
    Ws = max(120, ww2 + 8)
    body = symbol_group(INK, YELLOW, dx=(Ws - 120) / 2) + \
        f'<path d="{word2}" fill="{INK}" transform="translate({_fmt((Ws - ww2) / 2)} 84)"/>'
    out["volteye-logo-empile.svg"] = svg(Ws, 84 + cap2 + 6, body, "VoltEye")

    # icône d'application (512) : carré bleu arrondi, œil blanc, pupille jaune ; variante masquable plein cadre
    def icon(rounded, frac):
        s = 512 * frac / 120
        bg = f'<rect width="512" height="512" rx="{112 if rounded else 0}" fill="{BLUE}"/>'
        return bg + symbol_group(WHITE, YELLOW, simple=False, dx=(512 - 120 * s) / 2, dy=256 - 36 * s, scale=s)
    out["volteye-icone.svg"] = svg(512, 512, icon(True, 0.74), "VoltEye")
    out["volteye-icone-masquable.svg"] = svg(512, 512, icon(False, 0.6), "VoltEye")

    # favicon : tracé simplifié sur tuile bleue, lisible à 16 px
    s = 64 * 0.86 / 120
    fav = f'<rect width="64" height="64" rx="14" fill="{BLUE}"/>' + \
        symbol_group(WHITE, YELLOW, simple=True, dx=(64 - 120 * s) / 2, dy=32 - 36 * s, scale=s)
    out["volteye-favicon.svg"] = svg(64, 64, fav, "VoltEye")
    return out


def web_paths():
    """Tracés du symbole pour l'application web (même géométrie que les fichiers de marque)."""
    import json
    up, lo = lids()
    sup, slo = lids(amp=28, ripple=0)
    data = {"viewBox": "0 0 120 72", "axe": list(AXIS), "cy": CY, "paupiere": LID, "axe_epaisseur": AXIS_W, "pupille": PUPIL_R,
            "haut": up, "bas": lo, "simple": {"haut": sup, "bas": slo}}
    target = ROOT.parent / "web" / "src" / "data" / "logo.json"
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return target


if __name__ == "__main__":
    for name, content in build().items():
        (ROOT / name).write_text(content, encoding="utf-8")
        print(f"{name:40s} {len(content):6d} octets")
    print("tracés de l'application :", web_paths().relative_to(ROOT.parent))
