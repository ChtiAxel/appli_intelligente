"""Large language model adapter (asynchrone)."""

from __future__ import annotations

from .async_client import AsyncOllamaClient
from .ollama_wrapper_iut import OllamaResponseError

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

def _strip_markdown_fence(text: str) -> str:
    """Retire un éventuel bloc ```sql ... ``` renvoyé malgré la consigne."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


class LLMClient:
    """Adaptateur applicatif asynchrone autour d'Ollama."""

    def __init__(self, client: AsyncOllamaClient | None = None) -> None:
        self.client = client or AsyncOllamaClient()

    async def generate_sql(self, question: str, schema: str) -> str:
        """Génère une requête SQL en lecture seule depuis une question."""
        prompt = f"Schema autorise:\n{schema}\n\n{SQL_FEW_SHOTS}Question:\n{question}"
        for _ in range(2):
            response = await self.client.generate(
                prompt,
                system=SQL_SYSTEM_PROMPT,
                # No output-token cap; the request timeout still applies.
                options={"temperature": 0, "num_predict": -1},
                think=False,
            )
            sql = _strip_markdown_fence(response)
            if sql:
                return sql
        raise OllamaResponseError(
            "L'IA n'a renvoyé aucune requête SQL après deux tentatives. Veuillez réessayer."
        )
    async def generate_title(self, question: str) -> str:
        """Génère un titre très court (3 à 5 mots en français) pour nommer la discussion."""
        prompt = (
            "Tu es un assistant de synthèse. Donne un titre concis en français (maximum 4 ou 5 mots, sans ponctuation finale, sans guillemets, sans emoji) "
            f"pour résumer cette question d'utilisateur :\n{question}\nTitre :"
        )
        try:
            res = await self.client.generate(prompt, options={"temperature": 0.3})
            title = res.strip().strip('"\'').strip()
            # Nettoyer et tronquer si trop long
            if "\n" in title:
                title = title.split("\n")[0].strip()
            if len(title) > 40:
                title = title[:40].strip()
            return title if title else question[:35]
        except Exception:
            return question[:35]
