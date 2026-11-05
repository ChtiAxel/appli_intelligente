# SPRINT 02 — Moteur d'interrogation, Sécurité Applicative & Synthèse

> **Statut :** Clôturé (Rattrapage & consolidation)  
> **Référence d'évaluation :** Suivi du 01/11/2026 — 13 fichiers / 179 tests unitaires et d'intégration validés.

---

## 1. Cadre Agile

### Definition of Ready (DoR)
* Le besoin fonctionnel ou technique est formulé sous la forme standard « En tant que... je veux... afin de... ».
* Les entrées/sorties attendues sont identifiées (schéma de prompt, format des retours SQL).
* Les contraintes de sécurité (lecture seule, mots-clés interdits) sont spécifiées avant implémentation.

### Definition of Done (DoD)
* Code implémenté, typé et conforme aux conventions du projet.
* Tests unitaires et d'intégration associés écrits et passants à 100% en local.
* Non-régression validée sur la suite de tests complète (`pytest tests/`).
* Documentation utilisateur ou technique mise à jour.

---

## 2. User Stories & Preuves de Tests

| ID | User Story | Statut | Preuve de test / Fichier associé |
| :--- | :--- | :---: | :--- |
| **US-18** | En tant que système, je veux transmettre la question de l'utilisateur au LLM pour générer une requête SQL sécurisée. | **Terminé** | `tests/test_sql_generation.py`<br>`tests/test_ollama.py` |
| **US-19** | En tant que système, je veux exécuter la requête SQL validée sur le SGBD pédagogique via le module de stockage. | **Terminé** | `tests/test_storage.py` |
| **US-20** | En tant que système, je veux récupérer les jeux de résultats tabulaires bruts renvoyés par la base de données. | **Terminé** | `tests/test_storage.py`<br>`tests/test_core.py` |
| **US-21** | En tant que système, je veux gérer les exceptions d'exécution SQL sans bloquer l'application. | **Terminé** | `tests/test_core.py`<br>`tests/test_storage_security.py` |
| **US-22** | En tant que système, je veux transmettre les données tabulaires brutes à un second prompt LLM pour générer une réponse explicative et claire en français. | **Terminé** | `tests/test_pipeline.py`<br>`tests/test_core.py` |
| **US-23** | En tant que système, je veux formater les résultats en markdown propre pour un affichage direct dans les bulles du chat. | **Terminé** | `tests/test_ui_and_logging.py` |
| **US-24** | En tant qu'utilisateur, je veux obtenir une réponse combinant une synthèse textuelle claire et un tableau de données structuré. | **Terminé** | `tests/test_pipeline.py`<br>`src/NaturSQL/ui_gradio.py` |
| **US-25** | En tant qu'utilisateur, je veux pouvoir afficher ou masquer la requête SQL générée via un « Mode Avancé » pour un contrôle technique. | **Terminé** | `tests/test_ui_and_logging.py`<br>`src/NaturSQL/ui_gradio.py` |
| **US-26** | En tant que système, je veux sauvegarder l'historique réel des conversations et des requêtes en base de données pour alimenter dynamiquement la sidebar. | **Terminé** | `tests/test_storage.py`<br>`tests/test_ui_and_logging.py` |
| **US-27** | En tant qu'utilisateur, je veux pouvoir cliquer sur les anciennes conversations de la sidebar pour recharger leur contenu exact. | **Terminé** | `tests/test_ui_and_logging.py` |
| **US-29** *(Rattrapage)* | En tant qu'administrateur, je veux un contrôle d'accès basé sur les rôles (RBAC : ADMIN, PROF, SECRETAIRE) limitant l'accès au chat et aux fonctionnalités selon le profil. | **Terminé** | `tests/test_profile_chat_access.py`<br>`tests/test_auth.py` |
| **US-30** *(Rattrapage)* | En tant que système, je veux un durcissement de sécurité applicatif (interdiction stricte des mots-clés DDL/DML mutants, timeouts, sessions `READ ONLY`, quotas de lignes) pour bloquer les injections. | **Terminé** | `tests/test_storage_security.py`<br>`tests/test_auth_adversarial.py` |
| **US-31** *(Rattrapage)* | En tant que système, je veux une architecture de pipeline entièrement asynchrone (`asyncio.to_thread` pour la DB + client Ollama async) pour éviter tout blocage de l'UI. | **Terminé** | `tests/test_async_client.py`<br>`tests/test_pipeline.py` |

---

## 3. Report au Sprint 03

* **US-28 : Validation de bout en bout sur l'infrastructure réelle de l'IUT**  
  *Justification du report :* Le pipeline fonctionne en intégration locale simulée, mais la recette complète sur le serveur MariaDB réel et l'instance Ollama de l'IUT doit être documentée avec un jeu de données réel et un compte SGBD restreint (exigences du suivi enseignant du 01/11/2026). Reporté au **Sprint 03**.
