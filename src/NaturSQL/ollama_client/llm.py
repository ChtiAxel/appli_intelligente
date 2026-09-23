"""Large language model adapter."""

from .ollama_wrapper_iut import OllamaWrapper
from NaturSQL import config


class LLMClient:
    """Small application-facing adapter around the Ollama wrapper."""

    def __init__(self, client: OllamaWrapper | None = None) -> None:
        self.client = client or OllamaWrapper(
            base_url=config.OLLAMA_BASE_URL,
            timeout_s=config.OLLAMA_TIMEOUT_SECONDS,
        )

    def generate_sql(self, question: str, schema: str) -> str:
        """Generate a read-only SQL query from a natural-language question."""
        result = self.client.generate_text(
            model=config.OLLAMA_MODEL,
            system=(
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
            ),
            prompt=(
                f"Schema autorise:\n{schema}\n\n"
                "Exemple 1:\n"
                "Question: Quelles sont les séances de TD données par Aurélien Buret dans le cours Virtualisation avancée ?\n"
                "SQL: SELECT * FROM details WHERE prenom_ens = 'Aurélien' AND nom_ens = 'Buret' AND intitule_cours = 'Virtualisation avancée' AND type_seance LIKE 'TD%';\n\n"
                "Exemple 2:\n"
                "Question: Quels enseignants donnent des TP dans le cours Qualité de développement ?\n"
                "SQL: SELECT DISTINCT nom_ens, prenom_ens FROM details WHERE intitule_cours = 'Qualité de développement' AND type_seance LIKE 'TP%';\n\n"
                f"Question:\n{question}"
            ),
            options={"temperature": 0},
        )
        return result.response.strip()
