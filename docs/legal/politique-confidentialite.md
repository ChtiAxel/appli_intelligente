# Politique de confidentialité

## 1. Préambule et cadre juridique

La présente Politique de Confidentialité a pour vocation d'informer les utilisateurs de **NaturSQL** de la manière dont leurs données à caractère personnel sont collectées, traitées et protégées, en stricte conformité avec le **Règlement Général sur la Protection des Données (RGPD - Règlement UE 2016/679)** et la loi **Informatique et Libertés**.

Le service NaturSQL est développé au sein du Département Informatique de l'**Institut Universitaire de Technologie de Calais (Université du Littoral Côte d'Opale - ULCO)**.

---

## 2. Responsable du traitement

Le responsable du traitement des données est :
- **Département Informatique — IUT de Calais (ULCO)**
- **Adresse** : 19 Rue Ferdinand Buisson, 62228 Calais Cedex, France
- **Courriel de contact** : `iut-calais-info@univ-littoral.fr`
- **Délégué à la Protection des Données (DPO)** : DPO de l'Université du Littoral Côte d'Opale (`dpo@univ-littoral.fr`).

---

## 3. Données à caractère personnel collectées

Dans le cadre du principe de **minimisation des données (Art. 5-1 c du RGPD)**, seules les données strictement indispensables au fonctionnement du service sont collectées :

| Catégorie | Données précises | Finalité |
| :--- | :--- | :--- |
| **Identité du compte** | Prénom, Nom, Identifiant normalisé (`nom.prenom`), Rôle métier (`PROF`, `SECRETAIRE`, `ADMIN`) | Création, gestion du compte et personnalisation des accès |
| **Sécurité d'accès** | Empreinte de hachage sécurisée du mot de passe (via algorithme standardisé Werkzeug / PBKDF2-SHA256) | Authentification chiffrée |
| **Preuve de consentement** | Date et heure de validation du consentement RGPD (`rgpd_accepted_at`) | Traçabilité légale du consentement (Art. 7 du RGPD) |
| **Historique conversationnel** | Titres des discussions, questions posées en langage naturel, requêtes SQL générées et réponses | Fourniture de l'historique utilisateur dans la barre latérale |

> [!NOTE]
> Aucun cookie traceur publicitaire ou outil d'analyse tiers (type Google Analytics) n'est employé sur l'application. Aucun numéro de carte bancaire, moyen de paiement ou donnée financière n'est collecté.

---

## 4. Souveraineté de l'IA & Traitement des données

Un principe fondateur de NaturSQL réside dans la **souveraineté numérique et la confidentialité absolue** :
- **Traitement local exclusif** : Le modèle d'intelligence artificielle fonctionne via une instance conteneurisée **Ollama** déployée en local sur l'infrastructure de l'université.
- **Aucune fuite Cloud** : Aucune question utilisateur, aucune donnée issue de la base de données pédagogique `appia` ni aucun historique n'est transféré à des prestataires d'IA tiers (OpenAI, Anthropic, Google, Microsoft).
- **Protection par confinement SQL** : L'IA ne dispose que d'un utilisateur MariaDB restreint en lecture seule (`natursql_readonly`), interdisant toute modification ou altération des tables.

---

## 5. Base légale des traitements

Les traitements opérés par NaturSQL reposent sur :
1. **Le consentement explicite de l'utilisateur (Art. 6-1 a du RGPD)** : Recueilli lors de l'inscription via une case à cocher obligatoire et non pré-cochée.
2. **L'intérêt légitime (Art. 6-1 f du RGPD)** : Assurer la sécurité applicative, la prévention des attaques par force brute et le bon fonctionnement du service d'aide au requêtage.

---

## 6. Durée de conservation des données

- **Données de compte et profil** : Conservées pendant la durée d'activation du compte par l'utilisateur.
- **Historique des conversations** : Conservé tant que l'utilisateur ne supprime pas explicitement une conversation individuelle ou l'intégralité de son compte.
- **Suppression définitive** : L'utilisation de la fonction « Supprimer mon compte » entraîne l'effacement immédiat, complet et irréversible de l'intégralité des enregistrements en base de données (compte, conversations, messages).

---

## 7. Droits des utilisateurs et modalités d'exercice

Conformément à la réglementation européenne, vous disposez des droits suivants :

- **Droit d'accès (Art. 15)** : Vous pouvez consulter l'ensemble des informations rattachées à votre compte sur votre page profil.
- **Droit de rectification (Art. 16)** : Vous pouvez modifier à tout moment votre prénom, votre nom ou votre mot de passe depuis l'accordéon de votre profil.
- **Droit à l'effacement (« Droit à l'oubli » - Art. 17)** : Accessible directement en un clic via le bouton « Supprimer mon compte » dans la Zone de Danger de votre profil.
- **Droit à la portabilité (Art. 20)** : Vous pouvez télécharger l'intégralité de vos données personnelles et de votre historique au format JSON structuré grâce au bouton dédié « Télécharger mes données personnelles (JSON) ».
- **Droit de retrait du consentement (Art. 7-3)** : Le retrait de votre consentement s'exerce simplement et à tout instant par la clôture/suppression de votre compte.

Pour toute question ou exercice direct auprès du responsable de traitement, vous pouvez adresser un courriel à : `iut-calais-info@univ-littoral.fr` ou au DPO de l'établissement : `dpo@univ-littoral.fr`. Si vous estimez que vos droits ne sont pas respectés, vous conservez le droit d'introduire une réclamation auprès de la [CNIL (Commission Nationale de l'Informatique et des Libertés)](https://www.cnil.fr).
