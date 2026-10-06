# Documentation Utilisateur - NaturSQL

* **Version :** 1.0
* **Public cible :** Responsables pédagogiques, secrétariats, enseignants

## Sommaire
1. [Présentation générale](#1-presentation-generale)
2. [Lexique et définitions](#2-lexique-et-definitions)
3. [Accéder à l'application](#3-acceder-a-lapplication)
4. [Guide pas à pas](#4-guide-pas-a-pas)
   - [4.1 Créer un compte utilisateur](#41-creer-un-compte-utilisateur)
   - [4.2 Se connecter](#42-se-connecter)
   - [4.3 Consulter et modifier son profil](#43-consulter-et-modifier-son-profil)
   - [4.4 Utiliser le Chatbot et l'Historique (Sidebar)](#44-utiliser-le-chatbot-et-lhistorique-sidebar)
   - [4.5 Se déconnecter](#45-se-deconnecter)
5. [Comment bien formuler ses questions ?](#5-comment-bien-formuler-ses-questions)
6. [Exemples de questions types](#6-exemples-de-questions-types)
7. [Foire Aux Questions (FAQ) & Dépannage](#7-foire-aux-questions-faq--depannage)
8. [Assistance et contact](#8-assistance-et-contact)

---

## 1. Présentation générale

**NaturSQL** est un outil en ligne intuitif conçu pour faciliter la recherche d'informations sur les enseignements, les enseignants, les plannings et les maquettes pédagogiques de votre établissement.

Traditionnellement, l'accès à ces informations nécessite de maîtriser des outils informatiques complexes ou de manipuler manuellement de multiples tableurs. Grâce à NaturSQL, il vous suffit de **poser vos questions en français naturel**, comme vous le feriez avec un collègue, pour que l'assistant recherche automatiquement les données exactes et vous formule une réponse claire et synthétique.

---

## 2. Lexique et définitions

Pour faciliter votre lecture, voici quelques termes simples utilisés dans l'application :

* **Assistant intelligent :** Module logiciel capable de comprendre une question formulée en langage courant et de restituer la réponse correspondante.
* **Données pédagogiques :** Ensemble des informations enregistrées concernant les cours, matières, enseignants, volumes horaires (CM, TD, TP) et prérequis.
* **Historique (Sidebar) :** Panneau latéral qui conserve la trace de vos conversations passées.
* **Identifiant :** Nom d'utilisateur unique généré lors de votre inscription, utilisé pour vous connecter.
* **SQL :** Le code généré par l'IA pour interroger la base de données. Il est affiché par transparence au-dessus de vos résultats.

---

## 3. Accéder à l'application

Pour utiliser NaturSQL, vous n'avez besoin d'installer aucun logiciel sur votre poste :
1. Munissez-vous d'un navigateur web récent (Google Chrome, Mozilla Firefox, Microsoft Edge ou Safari).
2. Saisissez dans la barre d'adresse le lien communiqué par votre administrateur (par exemple : `http://localhost:7860`).
3. La page d'accueil de NaturSQL s'affiche instantanément.

---

## 4. Guide pas à pas

### 4.1 Créer un compte utilisateur

Lors de votre première visite, vous devez vous enregistrer pour accéder aux services.

1. Sur la page d'accueil, cliquez sur le bouton **« Créer un compte »**.
2. Remplissez le formulaire avec vos informations :
   - **Prénom** (ex. : *Jean*)
   - **Nom** (ex. : *Dupont*)
   - **Mot de passe** : Choisissez un mot de passe sécurisé (au moins 8 caractères, dont au moins une majuscule, un chiffre et un caractère spécial).
   - **Confirmer le mot de passe** : Retapez à l'identique votre mot de passe.
3. Cliquez sur le bouton **« S'inscrire »**.
4. Un message vous confirme la création du compte.

*(📷 [Cliquez ici pour aller à la page et prendre la capture d'écran de l'inscription](http://localhost:7860) : remplacez ensuite ce texte par l'image MkDocs)*

---

### 4.2 Se connecter

1. Sur le formulaire de connexion (**Sign In**), saisissez :
   - Votre **Prénom** (ex. : *Jean*).
   - Votre **Nom** (ex. : *Dupont*).
   - Votre **Mot de passe**.
2. Cliquez sur le bouton **« Se connecter »**.
3. Vous êtes automatiquement redirigé vers l'interface principale.

*(📷 [Cliquez ici pour aller à la page et prendre la capture d'écran de connexion](http://localhost:7860) : remplacez ensuite ce texte par l'image MkDocs)*

---

### 4.3 Consulter et modifier son profil

Une fois connecté, vous pouvez accéder à tout moment à vos informations.

1. **Consulter :** En haut à droite de l'écran, cliquez sur le bouton **« Mon Profil »** pour visualiser vos informations.
2. **Modifier ses informations :**
   - Sur la page Profil, cliquez sur **« Modifier le profil »**.
   - Ajustez votre prénom ou votre nom si nécessaire.
   - Cliquez sur le bouton **« Enregistrer »** pour valider les modifications.
3. **Retour** : Cliquez sur le bouton **« Retour aux conversations »** pour revenir à l'assistant.

*(📷 [Cliquez ici pour aller au profil et prendre la capture d'écran](http://localhost:7860) : remplacez ensuite ce texte par l'image MkDocs)*

---

### 4.4 Utiliser le Chatbot et l'Historique (Sidebar)

L'interface de conversation est divisée en deux parties : **la Sidebar (à gauche)** et **le Chatbot (à droite)**.

#### Poser une question au Chatbot
1. Dans la zone de conversation à droite, repérez le champ de saisie en bas.
2. Saisissez votre question en français courant.
3. Validez en appuyant sur la touche **Entrée** de votre clavier ou en cliquant sur le bouton noir d'envoi.
4. L'assistant analyse votre demande, et vous répond avec le code SQL généré et le résultat de la base de données.

#### Gérer son historique
1. **Nouvelle discussion :** Cliquez sur le bouton **« + »** en haut à gauche pour démarrer une nouvelle conversation vierge.
2. **Rechercher :** Utilisez la barre "Search" de la sidebar pour retrouver d'anciens chats.
3. **Reprendre un chat :** Cliquez sur un des chats listés dans la sidebar pour le recharger instantanément.

*(📷 [Cliquez ici pour aller à l'interface de chat et prendre la capture d'écran globale](http://localhost:7860) : remplacez ensuite ce texte par l'image MkDocs)*

---

### 4.5 Se déconnecter

Pour préserver la sécurité de vos informations, pensez à vous déconnecter lorsque vous quittez votre poste :
1. Cliquez sur **« Mon Profil »** en haut à droite.
2. Cliquez sur le bouton rouge **« Déconnexion »**.

---

## 5. Comment bien formuler ses questions ?

Pour que l'assistant vous réponde de la manière la plus exacte possible, suivez ces quelques recommandations :

- **Soyez précis sur les intitulés :** Mentionnez le nom de la matière, le type de cours ou l'année universitaire si vous la connaissez.
  - *Moins efficace :* « Qui donne des cours ? »
  - *Très efficace :* « Quels enseignants interviennent en travaux pratiques (TP) pour la matière Informatique cette année ? »
- **Évitez les formulations vagues :** Précisez si vous souhaitez une liste de noms, un volume d'heures ou une date.
- **Analysez la réponse SQL :** Si le résultat texte vous paraît incomplet, vérifiez le bloc de code SQL généré juste au-dessus. Il indique exactement comment la base a été interrogée.

---

## 6. Exemples de questions types

Voici quelques exemples concrets que vous pouvez poser directement à NaturSQL :

| Thème recherché | Exemple de question à poser |
| :--- | :--- |
| **Affectation des enseignants** | *« Quels sont les enseignants de TP en informatique ? »* |
| **Volumes horaires** | *« Quel est le volume total d'heures de cours magistraux dispensé par M. Martin ? »* |
| **Enseignants vacataires** | *« Donne-moi la liste des enseignants vacataires intervenant au département. »* |
| **Maquettes et matières** | *« Quelles sont les matières dispensées au semestre 1 ? »* |
| **Prérequis pédagogiques** | *« Quels sont les prérequis nécessaires pour suivre le module d'algorithmique avancée ? »* |

---

## 7. Foire Aux Questions (FAQ) & Dépannage

**Q : L'assistant affiche une erreur SQL ou indique qu'il ne peut pas exécuter ma requête.**  
**R :** Par mesure de sécurité, l'application bloque automatiquement toute requête qui tente de modifier ou de supprimer des données (sécurité stricte en Lecture Seule). Si l'IA a généré une telle requête par erreur, essayez de reformuler votre question plus simplement.

**Q : Ma conversation a disparu de l'historique dans la Sidebar !**  
**R :** Vérifiez que vous n'avez pas tapé de texte par erreur dans la barre de recherche ("Search") de la sidebar, ce qui masquerait vos autres conversations. Sinon, cliquez sur le bouton "+" pour rafraîchir l'affichage.

**Q : L'assistant indique qu'aucune donnée n'a été trouvée, pourtant je suis sûr de moi.**  
**R :** Essayez de reformuler votre phrase sans utiliser d'abréviations ambiguës. Notez également que l'assistant base ses réponses **exclusivement sur les données enregistrées**. Si une information n'a pas encore été saisie, elle ne pourra pas être devinée.

**Q : Que faire si un message d'erreur rouge s'affiche lors de mon inscription ?**  
**R :** Vérifiez les critères de votre mot de passe. Il doit obligatoirement faire 8 caractères minimum et contenir au moins 1 majuscule, 1 chiffre et 1 caractère spécial (ex: `!`, `?`, `@`).

**Q : J'ai oublié mon identifiant de connexion.**  
**R :** Votre identifiant correspond à votre Prénom et votre Nom saisis lors de votre enregistrement.

---

## 8. Assistance et contact

Si vous rencontrez une difficulté non répertoriée dans ce guide ou pour toute demande d'évolution, vous pouvez contacter l'équipe support :

* **Support pédagogique & technique :** `support-pedagogie@iut-calais.fr`
* **Équipe de développement :** Axel Nave, Raphael Deroo, Rémy Rampelberghe, Noa Gaillard
