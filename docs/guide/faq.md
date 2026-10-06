# Foire Aux Questions (FAQ) & Dépannage

Retrouvez ici les réponses aux questions les plus fréquentes ainsi que la marche à suivre en cas de problème lors de l'utilisation de NaturSQL.

---

## 💡 Questions Générales

??? question "Comment fonctionne NaturSQL sans que j'aie besoin de taper du SQL ?"
    NaturSQL utilise un modèle d'intelligence artificielle hébergé localement qui analyse votre phrase en français, consulte la structure de la base de données, génère automatiquement la requête technique adaptée (qui s'affichera dans le chat), l'exécute de façon sécurisée en lecture seule, puis vous restitue la réponse sous forme de texte clair.

??? question "Mes questions ou données personnelles sont-elles envoyées sur des serveurs externes ?"
    Non. Le modèle d'intelligence artificielle est opéré localement sur nos propres serveurs. Aucune donnée d'enseignement ni information relative aux utilisateurs n'est transmise à des tiers ou à des services cloud externes.

---

## 🛠️ Dépannage & Erreurs Courantes

??? failure "L'assistant affiche une erreur SQL ou indique un refus (Permission Denied) !"
    Par mesure de sécurité stricte, l'application bloque automatiquement toute requête qui tente de modifier ou de supprimer des données (seule la lecture est autorisée). Si l'IA a généré une telle requête par erreur en pensant vous aider, l'exécution est bloquée pour protéger les données. Reformulez votre question plus simplement.

??? failure "L'assistant me dit qu'il n'a trouvé aucun résultat"
    1. **Vérifiez l'orthographe du nom ou de la matière** : assurez-vous que le nom du professeur ou de l'enseignement est correctement écrit.
    2. **Précisez l'année scolaire** : essayez d'ajouter l'année souhaitée (ex. : *« pour l'année 2024-2025 »*).
    3. **Reformulez avec des termes plus larges** : par exemple, remplacez une abréviation peu courante par son libellé complet.

??? failure "Ma conversation a disparu de la Sidebar !"
    Vérifiez que vous n'avez pas tapé de texte par erreur dans la barre de recherche ("Search") de la sidebar à gauche, ce qui masquerait vos autres conversations. Si la barre est vide, cliquez sur le bouton "+" pour rafraîchir l'affichage global.

??? failure "Erreur de connexion (identifiant ou mot de passe incorrect)"
    * Vérifiez que vous avez bien saisi votre **Prénom** et votre **Nom** dans les champs respectifs.
    * Prenez garde au verrouillage des majuscules lors de la saisie de votre mot de passe.
    * Si le problème persiste, rafraîchissez la page (`F5`) ou tentez de recréer un compte via le formulaire d'inscription.

??? failure "La page semble figée ou met trop de temps à répondre"
    * Lors d'une première interrogation complexe, le modèle d'intelligence artificielle peut mettre quelques secondes à s'initialiser.
    * Un timeout strict bloque les requêtes SQL dépassant 3 secondes pour ne pas surcharger le serveur. 
    * Si aucune réponse n'apparaît au bout de 30 secondes, rechargez la page de votre navigateur.

---

## 📞 Support & Assistance

Si vous ne trouvez pas de réponse à votre question ou si vous constatez une anomalie :

* 📧 **Email d'assistance pédagogique** : `support-pedagogie@iut-calais.fr`
* 🛠️ **Équipe de développement** :
  * Axel NAVE
  * Raphael DEROO
  * Rémy RAMPELBERGHE
  * Noa GAILLARD
* 🕒 **Plages de disponibilité** : Du lundi au vendredi, de 8h30 à 17h30
