__Cahier des charges :__

1. Objectifs du projet
Concevoir une application web ergonomique permettant aux utilisateurs (responsables pédagogiques, secrétariats, enseignants) d'interroger une base de données relationnelle complexe (services enseignants, maquettes, prérequis) en langage naturel, en s'appuyant sur un LLM via Ollama.


2. Architecture logicielle (Structure des répertoires)
L'application doit respecter la structure modulaire recommandée :

src/
│
├─ NaturSQL/                 # Module dédié au sujet
│   ├─ service/              # Logique métier pure
│   │   ├─ __init__.py
│   │   ├─ core.py           # Traduction NL -> SQL, exécution sécurisée et reformulation
│   │   └─ utils.py
│   │
│   ├─ storage/              # Accès à la BDD relationnelle
│   │   ├─ __init__.py
│   │   └─ base.py           # Connexion SQL et exécution en lecture seule
│   │
│   ├─ ollama_client/        # Wrapper LLM
│   │   ├─ __init__.py
│   │   ├─ base.py           # Interface Python
│   │   ├─ llm.py            # Implémentation pour la génération SQL et la synthèse
│   │   └─ embedding.py      # (Optionnel selon le besoin de RAG)
│   │
│   ├─ ui_gradio.py          # Interface utilisateur (Gradio) connectée au service
│   └─ config.py             # Gestion des variables d'environnement (pydantic-settings)
│
└─ shared/                   # Code partagé
    └─ logging.py
docker/
    └─ Dockerfile
docker-compose.yml


3. Fonctionnalités et Interfaces (UI)

A. Authentification & Profil
Interface Register / Connexion : Formulaire simple d'accès.

Profil utilisateur : - Consultant (accès aux interfaces de requêtage métier).
                     - Affichage des informations de compte.


B. Page Principale (Home / Chat)
Conversation vierge : Affichage d'une nouvelle session de chat prête à l'emploi dès le lancement.

Historique des conversations : Sauvegarde et affichage des sessions de questions-réponses précédentes.

Accès au profil : Navigation fluide vers la page de gestion du profil.


C. Cœur Métier : Langage Naturel vers SQL (via Ollama)
Saisie utilisateur : Poser une question métier en français (ex. : « Quels sont les enseignants de TP... »).

Traitement par le LLM (Ollama) :

Transmission du schéma relationnel au modèle.

Génération d'une requête SQL sécurisée.

Validation et exécution de la requête sur la base de données.

Restitution : Traduction des résultats en une réponse synthétique et claire en français.


4. Contraintes techniques & Déploiement (Docker)
Ollama : Connexion au serveur distant ou conteneurisé existant via une variable d'environnement (ex: OLLAMA_HOST).

Conteneurisation (Docker & Docker-Compose) :

Un fichier Dockerfile pour builder l'application Python/Gradio.

Un docker-compose.yml pour orchestrer l'application web et potentiellement la base de données associée.