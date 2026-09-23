"""Application configuration loaded from environment variables."""

import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Base de données pédagogique "appia" (MariaDB) - voir docker-compose.yml
# Table d'authentification : `utilisateurs` (nom_util, mdp, id_ens, admin, vacataire, budget)
# Table de profil liée     : `enseignants` (id_ens, nom_ens, prenom_ens, mail_ens, ...)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "appia")
DB_USER = os.getenv("DB_USER", "appia")
DB_PASSWORD = os.getenv("DB_PASSWORD", "appia_password")
