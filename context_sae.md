# Contexte et objectifs généraux
L'objectif central de cette SAÉ est de concevoir et développer des applications logicielles complètes intégrant des briques d'intelligence artificielle comme des services applicatifs. Il ne s'agit ni d'entraîner ou de réentraîner des modèles de deep learning, ni de concevoir des architectures agentiques complexes ou autonomes. La démarche consiste à exploiter la puissance de modèles existants (LLM, VLM, Embeddings) pour déléguer des tâches sémantiques.

# Infrastructure et contraintes
- **Souveraineté et infrastructure** : Tout tourne en local sur l'infrastructure de l'IUT.
- **Communication** : API REST avec une instance locale Ollama.
- **Modèles imposés** :
  - **LLM** (texte/raisonnement) : `gemma4:12b`
  - **VLM** (vision) : `qwen3-vl:instruct`
  - **Embedding** : `embeddinggemma`

# Objectif du Groupe 4 (NaturSQL)
Concevoir une interface web permettant d'interroger une base de données relationnelle complexe (services enseignants, maquettes pédagogiques, prérequis, affectations) en **langage naturel**.
Le système utilise un LLM pour traduire une question métier en un plan d'exécution SQL sécurisé, et interpréter les résultats.

**Exemple de requête** : « Quels sont les enseignants de TP qui interviennent dans un module dont le prérequis est l'algorithmique avancée ? »
**Traduction LLM** : Connaissance du schéma -> Requête SQL (lecture seule) -> Résultats -> Synthèse texte + tableaux.

## Fonctionnalités principales
1. **Pipeline Text-to-SQL** : Injection dynamique du schéma, génération SQL, sécurité (lecture seule).
2. **Exécution et synthèse** : Exécution sur la BDD, récupération des résultats, mise en forme LLM.
3. **Interface Web** : Chatbot (Gradio), affichage des requêtes SQL et des tableaux.

# Architecture imposée
- **UI (Gradio)** : Pure Python (pas de JS/HTML complexe), `Blocks`, `Chatbot`, `Dataframe`.
- **Service** : Logique métier pure, sans UI ni HTTP, renvoie des JSON-serialisables.
- **IA-Adapter (Ollama)** : Wrapper asynchrone (BaseLLM, BaseVLM) injecté dans les services.
- **Storage Layer** : BDD relationnelles (MariaDB/SQLite), vectorielles, cache.

## Structure de répertoires obligatoire
```text
src/
├─ NaturSQL/                 # Sujet du groupe 4
│   ├─ service/              # Logique métier pure (core.py, utils.py)
│   ├─ storage/              # Accès BDD (base.py)
│   ├─ ollama_client/        # Wrapper IA (base.py, llm.py, vlm.py, embedding.py)
│   ├─ ui_gradio.py          # Point d'entrée UI -> Service
│   └─ config.py             # Configuration (pydantic-settings)
└─ shared/                   # Code partagé (ex: logging.py)
docker/
    └─ Dockerfile
docker-compose.yml
```

## Règles de développement
- L'UI ne doit **jamais** toucher Ollama directement. Elle passe par les Services.
- `server_name="0.0.0.0"` dans Gradio pour l'accès Docker.
- Retourner **uniquement** des objets sérialisables en JSON depuis la couche Service.
- Utiliser `gr.update` pour figer l'UI pendant le traitement IA.
- Toujours appliquer les conventions Git (branches, commits, etc.).
