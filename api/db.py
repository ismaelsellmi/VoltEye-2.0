"""Connexion à la base TimescaleDB et petites aides de requête."""
import os
import re
import time
from pathlib import Path

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://volteye:volteye@127.0.0.1:55432/volteye")
SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"

_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return _engine


def wait_for_db(timeout=60):
    t0 = time.time()
    while True:
        try:
            with engine().connect() as cx:
                cx.execute(text("SELECT 1"))
            return
        except Exception:
            if time.time() - t0 > timeout:
                raise
            time.sleep(1)


def split_sql(sql):
    """Découpe un script SQL en instructions, en respectant les blocs $$ … $$."""
    out, buf, in_dollar = [], [], False
    for line in sql.splitlines():
        if line.strip().startswith("--") and not in_dollar:
            continue
        buf.append(line)
        in_dollar ^= line.count("$$") % 2 == 1
        if not in_dollar and line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt.strip(";").strip():
                out.append(stmt)
            buf = []
    return out


def ensure_schema():
    """Crée le schéma s'il manque (utile hors Docker, où l'init de l'image ne s'exécute pas)."""
    with engine().connect() as cx:
        exists = cx.execute(text("SELECT to_regclass('public.site')")).scalar()
    if exists:
        return False
    with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as cx:
        for stmt in split_sql(SCHEMA.read_text(encoding="utf-8")):
            cx.exec_driver_sql(stmt)
    return True


def migrate():
    """Évolutions de schéma sur une base déjà créée (idempotent)."""
    with engine().begin() as cx:
        cx.execute(text("ALTER TABLE event ADD COLUMN IF NOT EXISTS gradcam real[]"))


def rows(sql, **params):
    with engine().connect() as cx:
        return [dict(r._mapping) for r in cx.execute(text(sql), params)]


def scalar(sql, **params):
    with engine().connect() as cx:
        return cx.execute(text(sql), params).scalar()


def safe_select(sql, limit=200):
    """Exécute une requête SELECT unique en lecture seule (outil SQL de l'assistant)."""
    q = sql.strip().rstrip(";")
    if ";" in q or not re.match(r"(?is)^\s*(select|with)\b", q):
        raise ValueError("Seules les requêtes SELECT uniques sont autorisées.")
    with engine().connect() as cx:
        cx.execute(text("SET TRANSACTION READ ONLY"))
        cx.execute(text("SET LOCAL ROLE volteye_lecture"))
        cx.execute(text("SET LOCAL statement_timeout = 5000"))
        res = cx.execute(text(f"SELECT * FROM ({q}) AS r LIMIT {int(limit)}"))
        return [dict(r._mapping) for r in res]
