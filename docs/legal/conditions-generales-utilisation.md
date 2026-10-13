# Conditions générales d’utilisation (CGU)

## 1. Objet

Les présentes Conditions Générales d’Utilisation (CGU) encadrent l’accès et l’utilisation de l’application **NaturSQL**, outil d'assistance au requêtage en langage naturel de bases de données relationnelles développé au sein de l'IUT de Calais (Université du Littoral Côte d'Opale).

Toute création de compte ou utilisation du service implique l’acceptation pleine, entière et sans réserve des présentes CGU ainsi que de la [Politique de confidentialité](politique-confidentialite.md).

---

## 2. Description du service

NaturSQL permet aux utilisateurs autorisés (enseignants, secrétariats, personnels administratifs) d'interroger la base de données pédagogique universitaire en posant des questions en langage naturel (français). 

Le système s'appuie sur :
- Un modèle de langage local (Ollama) traduisant la demande métier en syntaxe SQL sécurisée.
- Une exécution confinée en lecture seule stricte (`SELECT` uniquement).
- Une synthèse claire des résultats accompagnée de visualisations tabulaires.

---

## 3. Accès au service et création de compte

1. **Conditions d'accès** : L'accès au service est réservé aux membres autorisés dans le cadre pédagogique ou institutionnel.
2. **Inscription** : Lors de la création de son compte, l'utilisateur renseigne obligatoirement son prénom, son nom, et un mot de passe robuste respectant la politique de sécurité (minimum 8 caractères, au moins une majuscule, un chiffre et un caractère spécial).
3. **Consentement obligatoire** : L'inscription nécessite le consentement préalable et explicite de l'utilisateur aux présentes CGU et au traitement de ses données personnelles.
4. **Identifiants** : L'utilisateur est seul responsable de la confidentialité de ses identifiants et de toute activité effectuée depuis sa session.

---

## 4. Règles d'usage et engagements de l'utilisateur

L'utilisateur s'engage à utiliser le service de manière responsable et loyale. Il s'interdit expressément de :
- Tenter de contourner les mécanismes de sécurité mis en place (injections SQL, tentatives d'altération de la base `appia`).
- Soumettre des requêtes contenant des propos injurieux, diffamatoires ou contraires à l'ordre public.
- Exploiter le système de façon abusive par des requêtes automatisées de nature à saturer l'infrastructure locale de calcul (serveur Ollama).
- Partager ou céder ses accès à des tiers non habilités.

---

## 5. Propriété intellectuelle

L'ensemble des composants logiciels, modèles de prompts, interfaces et documentations de NaturSQL sont protégés au titre du droit d'auteur. Toute extraction non autorisée des données pédagogiques ou réutilisation commerciale est formellement prohibée.

---

## 6. Protection des données personnelles & Droits des utilisateurs

Conformément au RGPD :
- Les données recueillies sont strictement limitées aux besoins de fonctionnement du service (minimisation).
- L'utilisateur dispose à tout moment d'un **Droit à l'effacement (Art. 17)** via le bouton « Supprimer mon compte » présent sur son profil, entraînant la purge immédiate et irréversible de l'ensemble de ses discussions.
- L'utilisateur bénéficie d'un **Droit à la portabilité (Art. 20)** lui permettant de télécharger à tout instant l'intégralité de ses données personnelles et historiques sous format JSON structuré.

---

## 7. Disponibilité et responsabilité

NaturSQL étant un projet issu d'une SAÉ universitaire, aucune garantie de disponibilité ininterrompue n'est apportée. L'équipe pédagogique et les développeurs ne sauraient être tenus responsables d'éventuelles indisponibilités temporaires liées à la maintenance de l'infrastructure de l'IUT.

---

## 8. Droit applicable et juridiction compétente

Les présentes CGU sont soumises au droit français. En cas de différend non résolu à l'amiable, les juridictions compétentes du ressort de l'Université du Littoral Côte d'Opale seront seules compétentes.
