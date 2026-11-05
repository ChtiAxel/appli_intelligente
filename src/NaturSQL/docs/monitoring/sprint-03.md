# SPRINT 03 — Sécurité SGBD réelle, Intégration Continue (CI) & Recette IUT

> **Statut :** En cours (Objectifs prioritaires du suivi enseignant du 01/11/2026)  
> **Objectif :** Résoudre les 3 points « Partiel » du bilan du 01/11/2026 pour sécuriser une validation 100% conforme.

---

## 1. Cadre Agile

### Definition of Ready (DoR)
* L'US répond aux 3 priorités impératives fixées par l'audit du 01/11/2026.
* Les dépendances d'infrastructure (accès SGBD MariaDB, conteneur Docker, secrets GitHub Actions) sont identifiées.
* Les critères d'acceptation et les cas de panne/refus sont documentés avant implémentation.

### Definition of Done (DoD)
* Code implémenté et testé sur l'infrastructure cible.
* Workflow GitHub Actions au vert avec exécution complète de `pytest` (tests unitaires, refus SQL, cas d'erreur).
* Preuve d'exécution et traces de recette consignées dans la documentation du dépôt.
* Revue de code effectuée et validée par au moins un pair avant merge sur `main`.

---

## 2. Backlog du Sprint 03

### US-32 : Compte SGBD dédié en lecture seule & restriction effective des tables
* **En tant que** responsable de la sécurité des données,
* **Je veux** que la fonction `get_query_connection()` utilise des identifiants SGBD dédiés restreints (`GRANT SELECT` uniquement sur les tables autorisées) plutôt que le compte applicatif principal (`DB_USER`),
* **Afin de** garantir l'étanchéité des données au niveau du moteur SQL (MariaDB), même en cas de contournement des filtres applicatifs.
* **Critères d'acceptation :**
  1. Un utilisateur SGBD dédié (ex: `natursql_readonly`) est configuré dans `docker/init.sql` et `.env.example`.
  2. Les permissions sont limitées à `SELECT` uniquement sur les tables métiers (`ALLOWED_TABLES`). Tout accès aux tables système, métadonnées sensibles ou tables d'authentification (`users`) est rejeté par MariaDB (erreur `1142: SELECT command denied`).
  3. `get_query_connection()` utilise exclusivement ces identifiants pour exécuter le SQL généré par le LLM.
  4. Un test d'intégration automatisé prouve le refus d'accès par MariaDB lors d'une tentative de lecture d'une table non autorisée.

---

### US-33 : Pipeline d'Intégration Continue (CI) avec exécution automatique de la suite Pytest
* **En tant que** développeur,
* **Je veux** que chaque Pull Request et push sur `main` exécute l'intégralité des 179 tests applicatifs (`pytest`) dans GitHub Actions,
* **Afin de** valider automatiquement la robustesse du code, les refus d'injections SQL et la gestion des pannes sans se limiter au simple déploiement de MkDocs.
* **Critères d'acceptation :**
  1. Le fichier `.github/workflows/ci.yml` (ou équivalent) exécute les tests unitaires et de sécurité sous Python 3.11/3.12.
  2. Les tests incluent la validation des cas limites, des refus SQL, et la simulation des pannes Ollama/DB via mocks.
  3. Le badge CI dans le `README.md` reflète le statut réel d'exécution des tests.
  4. L'étape de déploiement MkDocs ne s'exécute que si tous les tests applicatifs sont passés avec succès.

---

### US-28 : Cahier de recette et validation du parcours utilisateur de bout en bout sur l'infra IUT
* **En tant que** client / évaluateur pédagogique,
* **Je veux** un rapport de recette documenté validant le parcours complet *Question en français $\rightarrow$ Génération SQL $\rightarrow$ Tableau de données $\rightarrow$ Synthèse textuelle*,
* **Afin d'** avoir la preuve formelle du bon fonctionnement sur la base MariaDB et l'instance Ollama réelles de l'IUT.
* **Critères d'acceptation :**
  1. Au moins 5 scénarios métiers réels sont testés (questions simples, jointures, agrégations, cas sans résultat, question hors périmètre).
  2. Pour chaque scénario, le cahier de recette consigne : la question initiale, le SQL généré, le résultat brut tabulaire et la synthèse en langage naturel.
  3. Le comportement en cas d'erreur (erreur SQL, timeout, refus de permission) affiche un message utilisateur explicite et élégant sans plantage de l'interface.
  4. Le document de recette est versionné dans `src/NaturSQL/docs/recette_iut.md` avec captures d'écran et traces réelles.
