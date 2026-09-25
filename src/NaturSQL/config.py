"""Configuration de l'application, chargée depuis le fichier .env.

Le fichier .env (à la racine du projet, ignoré par git) contient les
secrets : identifiants de la BDD, URL d'Ollama, etc. Voir .env.example.

Les variables déjà définies dans l'environnement (ex. par docker-compose)
sont prioritaires sur celles du .env.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Racine du projet : src/NaturSQL/config.py -> ../../
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _require(name: str) -> str:
    """Retourne la variable `name` ou lève une erreur explicite si elle manque."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variable d'environnement manquante : {name}. "
            "Copiez .env.example en .env et renseignez-la."
        )
    return value


# --- Ollama ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# --- Base de données pédagogique "appia" (MariaDB) ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = _require("DB_NAME")
DB_USER = _require("DB_USER")
DB_PASSWORD = _require("DB_PASSWORD")
