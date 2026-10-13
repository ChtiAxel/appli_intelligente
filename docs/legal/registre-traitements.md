# Registre des activités de traitement (Article 30 du RGPD)

> **Document de conformité réglementaire** établi au titre de l'Article 30 du Règlement (UE) 2016/679 (Règlement Général sur la Protection des Données).

---

## Fiche de Traitement : NATURSQL-01

### 1. Responsable du traitement
- **Organisme** : Université du Littoral Côte d'Opale (ULCO) — IUT de Calais, Département Informatique.
- **Adresse** : 19 Rue Ferdinand Buisson, 62228 Calais Cedex, France.
- **Représentant opérationnel** : Équipe pédagogique SAÉ Application Intelligente & Équipe NaturSQL (Groupe 4).
- **Contact DPO** : `dpo@univ-littoral.fr`.

---

### 2. Finalités du traitement
- **Finalité principale** : Traduction automatique de requêtes métier en langage naturel (français) vers des requêtes SQL pour interroger une base de données relationnelle pédagogique universitaire.
- **Finalités secondaires** :
  - Authentification et gestion des sessions des utilisateurs autorisés (enseignants, secrétariat, administration).
  - Gestion de l'historique des conversations pour permettre la reprise des échanges.
  - Prévention des abus et sécurisation de l'accès aux bases de données universitaires.

---

### 3. Catégories de personnes concernées
- Étudiants et enseignants membres du projet.
- Personnels administratifs et pédagogiques de l'IUT utilisateurs de l'outil.

---

### 4. Catégories de données à caractère personnel traitées

| Type de donnée | Données collectées | Base légale (Art. 6 RGPD) |
| :--- | :--- | :--- |
| **Données d'identification** | Prénom, Nom, Identifiant applicatif (`nom.prenom`), Rôle métier | Consentement (Art. 6-1 a) |
| **Données d'authentification** | Mot de passe chiffré par empreinte de hachage (Werkzeug PBKDF2) | Exécution du service |
| **Traçabilité du consentement** | Horodatage de validation des CGU et politique de confidentialité (`rgpd_accepted_at`) | Obligation légale (Art. 7-1) |
| **Données d'usage & Requêtes** | Questions en langage naturel posées, requêtes SQL générées par l'IA, réponses synthétisées | Consentement / Intérêt légitime |
| **Données de profil optionnelles** | Avatar utilisateur (URL ou initiales vectorielles) | Consentement |

---

### 5. Destinataires des données
- **Internes** : Uniquement l'utilisateur connecté pour ses propres conversations et les administrateurs techniques de l'IUT.
- **Destinataires externes / Tiers** : **AUCUN**.
- **Transferts hors Union Européenne** : **AUCUN**. Le modèle LLM tourne intégralement en local sur serveur Ollama (infrastructure souveraine française).

---

### 6. Délais prévus pour l'effacement (Durées de conservation)

- **Comptes utilisateurs** : Conservés jusqu'à la demande de suppression par l'utilisateur.
- **Conversations & Messages** : Conservés jusqu'à suppression manuelle de la conversation ou suppression globale du compte.
- **Procédure d'effacement automatique** : La fonction « Supprimer mon compte » exécute une suppression atomique en cascade (`DELETE CASCADE`) purgeant simultanément le compte, les discussions et les messages de la base de données.

---

### 7. Mesures de sécurité techniques et organisationnelles (Art. 32 du RGPD)

1. **Sécurité du stockage des mots de passe** : Hachage avec sel par algorithme cryptographique robuste (aucun mot de passe stocké en clair).
2. **Cloisonnement des privilèges SQL (Principe de moindre privilège)** :
   - L'IA exécute ses requêtes via un utilisateur MariaDB dédié (`natursql_readonly`) doté uniquement du privilège `SELECT` sur les tables pédagogiques.
   - Les commandes destructives (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`) sont interdites au niveau du moteur de base de données.
   - Timeout strict d'exécution (3 secondes) et limitation du volume de retour (50 lignes maximum).
3. **Absence de télémétrie externe** : Aucun script d'analyse tiers ni cookie de pistage publicitaire.
4. **Droit à la portabilité (Art. 20)** : Fonctionnalité native d'export de l'intégralité des données en format standardisé JSON téléchargeable à tout moment.
