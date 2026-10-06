# Original User Request

## Initial Request — 2026-10-02T07:18:15Z

This is a single self-contained fix; keep it small and focused.
Implémentation de la couche de stockage SQL sécurisée pour NaturSQL. Cela inclut la création d'un utilisateur MariaDB en lecture seule stricte, l'exécution sécurisée des requêtes avec des limites de temps/lignes, la gestion des exceptions, et la rédaction d'une suite de tests automatisés (pytest) pour garantir l'absence de failles.

Working directory: c:\Users\noaga\Desktop\BUT\Zone51\SAEia
Integrity mode: development

## Requirements

### R1. Initialisation de la BDD
Modifier le fichier d'initialisation SQL du conteneur Docker (ex: `init.sql`) pour y créer un utilisateur MariaDB 100% "Lecture Seule" (ex: `natursql_readonly` avec uniquement `GRANT SELECT` sur les tables pédagogiques).

### R2. Exécution sécurisée et limites
Modifier `src/NaturSQL/storage/db.py` (et `core.py` si nécessaire) pour que l'exécution des requêtes générées par l'IA utilise exclusivement ce compte "Lecture Seule".
Mettre en place un timeout strict pour l'exécution (ex: 3 secondes) et une limite sur le nombre de lignes retournées (ex: 50 max).

### R3. Gestion des exceptions
Intercepter toutes les erreurs de la base de données (syntaxe, timeout, droits refusés) et renvoyer une erreur formatée et propre, sans jamais faire planter l'application.

### R4. Tests de robustesse (pytest)
Créer une suite de tests dans le dossier `tests/` avec `pytest`. Ces tests doivent envoyer des requêtes malveillantes simulées (`DROP TABLE`, `DELETE`, requêtes sur des tables systèmes) et vérifier qu'elles sont bien refusées et gérées gracieusement.

## Acceptance Criteria

### Sécurité et DB
- [ ] Le compte en lecture seule est créé automatiquement à l'initialisation de MariaDB.
- [ ] L'application se connecte avec ce compte pour l'exécution des requêtes générées.

### Code et Fiabilité
- [ ] Une limite de temps et de volume de retour est appliquée sur les requêtes SQL de l'IA.
- [ ] Les requêtes de destruction de données échouent sans crash de l'application.

### Vérification
- [ ] La commande `pytest` exécute la nouvelle suite de tests avec succès (100% de réussite).
