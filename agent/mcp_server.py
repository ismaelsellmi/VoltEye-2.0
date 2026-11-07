"""Serveur MCP VoltEye : les outils de l'assistant énergie, ouverts aux assistants IA compatibles.

Le Model Context Protocol (MCP) est un standard ouvert qui donne à un assistant IA un accès contrôlé à des
outils. Ce serveur expose, en lecture seule, les mêmes outils que l'assistant intégré : indicateurs,
consommation hors production, anomalies, santé, prévision, planning, VoltEye Grid, évaluation,
documentation et requêtes SQL en lecture seule.

Usage :
  python -m agent.mcp_server                 (transport stdio, pour un client MCP de bureau)
  python -m agent.mcp_server --http 8765     (transport HTTP « streamable », point d'entrée /mcp)
Variable : DATABASE_URL (base VoltEye).
"""
import json
import sys

from mcp.server.mcpserver import MCPServer

from . import tools

mcp = MCPServer("VoltEye", instructions="Outils en lecture seule sur les données énergétiques VoltEye : atelier de "
              "référence (7 machines, un seul compteur) et 10 zones industrielles tunisiennes (VoltEye Grid). "
              "L'historique couvre novembre 2025 à octobre 2026.")


def _json(result):
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
def indicateurs(jours: int = 30) -> str:
    """Énergie, coût et CO₂ de l'atelier sur les derniers jours, et répartition par machine."""
    return _json(tools.indicateurs(jours))


@mcp.tool()
def hors_production(jours: int = 30, machine: str | None = None) -> str:
    """Énergie consommée hors des heures de production (nuits, week-ends, jours fériés), par machine."""
    return _json(tools.hors_production(jours, machine))


@mcp.tool()
def anomalies(machine: str | None = None, mois: str | None = None) -> str:
    """Gaspillages détectés (jours en alerte) avec cause, coût de l'excès et action recommandée.
    machine : four, compresseur, cnc, convoyeur, eclairage, soudage ou cvc ; mois : « février » ou « 2026-02 »."""
    return _json(tools.anomalies(machine, mois))


@mcp.tool()
def sante(machine: str | None = None) -> str:
    """État de santé des machines : score sur 100, dérive de la distorsion harmonique (THD), alertes."""
    return _json(tools.sante(machine))


@mcp.tool()
def prevision(jour: str | None = None) -> str:
    """Qualité de la prévision du lendemain, ou détail d'un jour de la période de test (AAAA-MM-JJ)."""
    return _json(tools.prevision(jour))


@mcp.tool()
def planning(jour: str | None = None) -> str:
    """Gains du planning optimisé des tâches flexibles, ou détail d'un jour ouvré (AAAA-MM-JJ)."""
    return _json(tools.planning(jour))


@mcp.tool()
def voltEye_grid() -> str:
    """Réduction de la pointe d'été agrégée de 10 zones industrielles grâce à la flexibilité coordonnée."""
    return _json(tools.voltEye_grid())


@mcp.tool()
def evaluation() -> str:
    """Résultats d'évaluation des modèles d'IA de VoltEye."""
    return _json(tools.evaluation())


@mcp.tool()
def recherche_documentation(question: str) -> str:
    """Recherche dans la documentation approuvée : méthodes, hypothèses, tarifs, actions recommandées."""
    return _json(tools.recherche_documentation(question))


@mcp.tool()
def requete_sql(requete: str) -> str:
    """Requête SELECT unique en lecture seule sur la base VoltEye (50 lignes au plus)."""
    return _json(tools.requete_sql(requete))


if __name__ == "__main__":
    if "--http" in sys.argv:
        port = int(sys.argv[sys.argv.index("--http") + 1]) if len(sys.argv) > sys.argv.index("--http") + 1 else 8765
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run()
