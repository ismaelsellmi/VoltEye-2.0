"""Recherche dans la documentation approuvée (RAG) : passages indexés dans PostgreSQL avec pgvector.

Corpus : documentation du dépôt (données, résultats, architecture) et fiches de connaissances de
l'assistant. Plongements : modèle multilingue local (paraphrase-multilingual-MiniLM-L12-v2, 384 dimensions,
ONNX via fastembed), sans appel à un service extérieur. Repli : recherche plein texte PostgreSQL (français).
"""
import os
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text

from api import db
from volteye.config import ROOT

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_DIR = Path(os.environ.get("VOLTEYE_MODELS", ROOT / "data" / "models"))
CORPUS = [ROOT / "agent" / "connaissances.md", ROOT / "docs" / "donnees.md", ROOT / "docs" / "resultats.md",
          ROOT / "docs" / "architecture.md"]
MAX_CHARS = 1400


@lru_cache(maxsize=1)
def embedder():
    from fastembed import TextEmbedding
    return TextEmbedding(MODEL, cache_dir=str(MODEL_DIR))


def _pieces(para):
    """Coupe un paragraphe plus long que MAX_CHARS par lignes ; un tableau garde son en-tête dans chaque morceau."""
    if len(para) <= MAX_CHARS:
        return [para]
    lines = para.splitlines()
    head = lines[:2] if len(lines) > 2 and lines[0].startswith("|") and set(lines[1]) <= set("|-: ") else []
    out, cur = [], list(head)
    for line in lines[len(head):]:
        if len(cur) > len(head) and len("\n".join(cur + [line])) > MAX_CHARS:
            out.append("\n".join(cur))
            cur = list(head)
        cur.append(line)
    out.append("\n".join(cur))
    return out


def chunks():
    """Découpe chaque document par section (titres ## ou ###), puis par paragraphes si la section est longue."""
    out = []
    for path in CORPUS:
        if not path.exists():
            continue
        doc = path.read_text(encoding="utf-8")
        name = path.name
        for part in re.split(r"\n(?=#{2,3} )", doc):
            lines = part.strip().splitlines()
            if not lines:
                continue
            title = lines[0].lstrip("# ").strip() if lines[0].startswith("#") else name
            body = "\n".join(lines[1:] if lines[0].startswith("#") else lines).strip()
            buf = ""
            for para in (p for block in body.split("\n\n") for p in _pieces(block)):
                if buf and len(buf) + len(para) > MAX_CHARS:
                    out.append((name, title, buf.strip()))
                    buf = ""
                buf += para + "\n\n"
            if buf.strip():
                out.append((name, title, buf.strip()))
    return out


def _vec(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def index(log=print):
    items = chunks()
    try:
        vectors = [_vec(v) for v in embedder().embed([f"{t}. {c}" for _, t, c in items])]
    except Exception as e:                           # modèle indisponible : index plein texte seulement
        log(f"Plongements indisponibles ({e.__class__.__name__}) : recherche plein texte.")
        vectors = [None] * len(items)
    with db.engine().begin() as cx:
        cx.execute(text("DELETE FROM doc_chunk"))
        for (src, title, content), v in zip(items, vectors):
            cx.execute(text("INSERT INTO doc_chunk (source, title, content, embedding) "
                            "VALUES (:s, :t, :c, CAST(:v AS vector))"), {"s": src, "t": title, "c": content, "v": v})
    log(f"Documentation indexée : {len(items)} passages.")
    return len(items)


def sync(log=print):
    """Réindexe si la base ne correspond plus aux documents (appelé au démarrage de l'API)."""
    stored = [(r["source"], r["title"], r["content"]) for r in db.rows("SELECT source, title, content FROM doc_chunk ORDER BY id")]
    if stored != chunks():
        return index(log)
    return len(stored)


def search(question, k=4, pool=8):
    """Recherche hybride : proximité sémantique (pgvector) et plein texte français, fusionnées par rang (RRF)."""
    if not db.scalar("SELECT count(*) FROM doc_chunk"):
        index(log=lambda *a: None)
    ranked = []
    if db.scalar("SELECT count(*) FROM doc_chunk WHERE embedding IS NOT NULL"):
        try:
            q = _vec(next(iter(embedder().embed([question]))))
            ranked.append((0.6, db.rows("""SELECT id FROM doc_chunk WHERE embedding IS NOT NULL
                                     ORDER BY embedding <=> CAST(:q AS vector) LIMIT :n""", q=q, n=pool)))
        except Exception:
            pass
    words = " | ".join(w for w in re.findall(r"\w{4,}", question.lower()))
    if words:
        ranked.append((1.0, db.rows("""SELECT id FROM doc_chunk
                                 WHERE to_tsvector('french', title || ' ' || content) @@ to_tsquery('french', :q)
                                 ORDER BY ts_rank(to_tsvector('french', title || ' ' || content), to_tsquery('french', :q)) DESC
                                 LIMIT :n""", q=words, n=pool)))
    score = {}
    for weight, lst in ranked:
        for rank, r in enumerate(lst):
            score[r["id"]] = score.get(r["id"], 0) + weight * 60 / (60 + rank)
    if not score:
        return []
    rows = {r["id"]: r for r in db.rows("SELECT id, source, title, content FROM doc_chunk WHERE id = ANY(:ids)", ids=list(score))}
    # couverture lexicale : part des mots de la question (racines de 5 lettres) présents dans le passage
    stems = {_plain(w)[:5] for w in re.findall(r"\w{4,}", question) if _plain(w) not in STOP}
    for i, r in rows.items():
        words = {_plain(w)[:5] for w in re.findall(r"\w{4,}", r["title"] + " " + r["content"])}
        score[i] += 2 * len(stems & words) / max(len(stems), 1)
    best = sorted(score, key=lambda i: -score[i])[:k]
    return [{"source": f"{rows[i]['source']} › {rows[i]['title']}", "extrait": rows[i]["content"],
             "score": round(score[i], 3)} for i in best]


STOP = {"pourquoi", "comment", "quand", "quel", "quelle", "quels", "quelles", "est-ce", "dans", "avec", "pour", "elle",
        "elles", "sont", "cette", "votre", "notre", "faut", "faire"}


def _plain(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
