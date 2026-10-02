"""Large language model adapter (asynchrone)."""

from __future__ import annotations

import json
from typing import Any, Sequence

from .async_client import AsyncOllamaClient

# Nombre maximal de lignes envoyées au LLM pour l'explication des résultats.
MAX_ROWS_FOR_EXPLANATION = 50

SQL_SYSTEM_PROMPT = (
    "Tu es un assistant SQL MariaDB. Genere uniquement une requete "
    "SELECT ou WITH validee a partir du schema fourni. "
    "Ne genere jamais INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, "
    "TRUNCATE, GRANT ou plusieurs requetes. Retourne uniquement le SQL, "
    "sans Markdown ni explication. Dans cette base, une intervention "
    "en TP correspond aux valeurs type_seance qui commencent par 'TP' "
    "(TPA, TPB, TPC, TPD ou TPE), pas a la valeur exacte 'TP'. "
    "Utilise LIKE 'TP%' pour ce cas. De meme, CM-APP commence par CM "
    "et les types SAE commencent par SAE. "
    "IMPORTANT 1 : Toujours utiliser le mot-clé DISTINCT lorsque la "
    "question demande 'quels enseignants', 'qui' ou une liste de personnes. "
    "IMPORTANT 2 : La table 'details' est une vue qui regroupe déjà "
    "le nom, prénom, le cours et le type de séance. Privilégie TOUJOURS "
    "une requête simple sur 'details' sans faire de JOIN inutiles. "
    "IMPORTANT 3 : Les colonnes 'nom_ens' et 'prenom_ens' contiennent "
    "respectivement le nom de famille seul et le prénom seul. "
    "Ne cherche jamais un prénom et un nom complets dans la même colonne."
)

SQL_FEW_SHOTS = (
    "Exemple 1:\n"
    "Question: Quelles sont les séances de TD données par Aurélien Buret dans le cours Virtualisation avancée ?\n"
    "SQL: SELECT * FROM details WHERE prenom_ens = 'Aurélien' AND nom_ens = 'Buret' AND intitule_cours = 'Virtualisation avancée' AND type_seance LIKE 'TD%';\n\n"
    "Exemple 2:\n"
    "Question: Quels enseignants donnent des TP dans le cours Qualité de développement ?\n"
    "SQL: SELECT DISTINCT nom_ens, prenom_ens FROM details WHERE intitule_cours = 'Qualité de développement' AND type_seance LIKE 'TP%';\n\n"
)

EXPLAIN_SYSTEM_PROMPT = (
    "Tu es un assistant qui explique des résultats de base de données à un "
    "utilisateur non technique. Réponds en français, en 2 à 5 phrases claires. "
    "Appuie-toi uniquement sur les données fournies : n'invente aucune valeur. "
    "Si les données sont vides, dis simplement qu'aucun résultat ne correspond. "
    "Ne réécris pas le tableau complet et ne parle pas de SQL."
)


def _strip_markdown_fence(text: str) -> str:
    """Retire un éventuel bloc ```sql ... ``` renvoyé malgré la consigne."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _rows_to_prompt(rows: Sequence[dict[str, Any]]) -> str:
    """Sérialise les lignes en JSON lisible (dates/décimaux convertis en texte)."""
    shown = list(rows[:MAX_ROWS_FOR_EXPLANATION])
    data = json.dumps(shown, ensure_ascii=False, default=str, indent=1)
    if len(rows) > len(shown):
        data += f"\n(... {len(rows) - len(shown)} lignes supplémentaires non affichées)"
    return data


class LLMClient:
    """Adaptateur applicatif : deux prompts asynchrones sur Ollama."""

    def __init__(self, client: AsyncOllamaClient | None = None) -> None:
        self.client = client or AsyncOllamaClient()

    async def generate_sql(self, question: str, schema: str) -> str:
        """Prompt 1 : génère une requête SQL en lecture seule depuis une question."""
        response = await self.client.generate(
            f"Schema autorise:\n{schema}\n\n{SQL_FEW_SHOTS}Question:\n{question}",
            system=SQL_SYSTEM_PROMPT,
            options={"temperature": 0},
        )
        return _strip_markdown_fence(response)

    async def explain_results(self, question: str, rows: Sequence[dict[str, Any]]) -> str:
        """Prompt 2 : rédige une synthèse en français à partir des données brutes."""
        response = await self.client.generate(
            f"Question de l'utilisateur :\n{question}\n\n"
            f"Nombre total de lignes : {len(rows)}\n"
            f"Données (JSON) :\n{_rows_to_prompt(rows)}\n\n"
            "Rédige la synthèse.",
            system=EXPLAIN_SYSTEM_PROMPT,
            options={"temperature": 0.2},
        )
        return response.strip()
