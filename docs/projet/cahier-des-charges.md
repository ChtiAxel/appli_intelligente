# Cahier des Charges du Projet

Ce document reprend les objectifs, l'architecture attendue et les contraintes techniques définis pour le projet **NaturSQL**.

---

## 1. Objectifs du projet

Concevoir une application web ergonomique permettant aux utilisateurs (responsables pédagogiques, secrétariats, enseignants) d'interroger une base de données relationnelle complexe (services enseignants, maquettes, prérequis) en langage naturel, en s'appuyant sur un LLM via Ollama.

---

## 2. Architecture logicielle (Structure des répertoires)

L'application respecte la structure modulaire suivante :

```text
src/
│
├─ NaturSQL/                 # Module dédié au sujet
│   ├─ service/              # Logique métier pure
│   │   ├─ core.py           # Traduction NL -> SQL, exécution sécurisée et reformulation
│   │   ├─ auth.py           # Gestion de l'authentification et des profils
│   │   └─ utils.py
│   │
│   ├─ storage/              # Accès à la BDD relationnelle
│   │   ├─ base.py           # Connexion SQL et exécution en lecture seule
│   │   └─ users.py          # Gestion des comptes utilisateurs
│   │
│   ├─ ollama_client/        # Wrapper LLM
│   │   ├─ base.py           # Interface Python
│   │   ├─ llm.py            # Implémentation pour la génération SQL et la synthèse
│   │   └─ embedding.py      # (Optionnel selon le besoin de RAG)
│   │
│   ├─ ui_gradio.py          # Interface utilisateur (Gradio) connectée au service
│   └─ config.py             # Gestion des variables d'environnement
│
└─ shared/                   # Code partagé
    └─ logging.py
```

---

## 3. Fonctionnalités et Interfaces (UI)

### A. Authentification & Profil
* **Interface Register / Connexion** : Formulaire simple d'accès avec validation des critères de mot de passe.
* **Profil utilisateur** : 
  * Rôle consultant (accès aux interfaces de requêtage métier).
  * Affichage et modification des informations de compte.

### B. Page Principale (Home / Chat)
* **Conversation vierge** : Affichage d'une nouvelle session de chat prête à l'emploi dès le lancement.
* **Historique des conversations** : Sauvegarde et affichage des sessions de questions-réponses précédentes.
* **Accès au profil** : Navigation fluide vers la page de gestion du profil.

### C. Cœur Métier : Langage Naturel vers SQL (via Ollama)
* **Saisie utilisateur** : Poser une question métier en français (ex. : *« Quels sont les enseignants de TP... »*).
* **Traitement par le LLM (Ollama)** :
  1. Transmission du schéma relationnel au modèle.
  2. Génération d'une requête SQL sécurisée en lecture seule (`SELECT`).
  3. Validation et exécution de la requête sur la base de données MariaDB `appia`.
* **Restitution** : Traduction des résultats en une réponse synthétique et claire en français.

---

## 4. Contraintes techniques & Déploiement

* **Ollama** : Connexion au serveur conteneurisé existant via variable d'environnement (`OLLAMA_BASE_URL`).
* **Conteneurisation (Docker & Docker-Compose)** :
  * Un fichier `Dockerfile` pour builder l'application Python/Gradio.
  * Un `docker-compose.yml` pour orchestrer l'application web et la base de données associée.
