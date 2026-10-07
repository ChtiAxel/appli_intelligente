<div align="center">
  <img src="docs/mockup/logo.png" alt="NaturSQL Logo" width="150" />
  <h1>NaturSQL</h1>
  <p><em>L'Intelligence Artificielle au service de votre Base de Données</em></p>
</div>

---

## 📖 À propos du projet

**NaturSQL** (Application Intelligente) est une application web qui traduit le langage naturel (français) en requêtes SQL. Ce projet a été conçu pour permettre aux utilisateurs sans connaissances techniques d'interroger directement une base de données complexe de manière intuitive et totalement sécurisée.

Ce projet est réalisé dans le cadre de la SAE "Application Intelligente".

### ✨ Fonctionnalités clés
- **Traduction IA locale** : Utilisation d'un modèle LLM local (Ollama) pour analyser les questions et générer le SQL approprié, garantissant la confidentialité des données (aucune donnée envoyée dans le cloud).
- **Interface Web Moderne** : Développée avec Gradio, comprenant une gestion complète de comptes utilisateurs (Inscription, Connexion, Profil).
- **Sécurité Stricte** : Exécution des requêtes dans un environnement confiné (compte MariaDB en lecture seule, timeout strict de 3 secondes, limitation à 50 lignes retournées).
- **Historique & Chat** : Interface de type "chatbot" permettant de retrouver facilement ses anciennes conversations via une barre de recherche.

---

## 🛠️ Stack Technique

- **Backend / Logique** : Python 3.12+
- **Frontend / UI** : Gradio
- **Base de données** : MariaDB (via `PyMySQL`)
- **Modèle IA** : Ollama (Gemma2 / Llama3 selon configuration)
- **Déploiement** : Docker & Docker Compose
- **Tests Qualité** : Pytest
- **Documentation** : MkDocs

---

## 🚀 Installation & Lancement (Environnement de dev)

### Prérequis
- [Docker](https://www.docker.com/) et Docker Compose installés sur votre machine.
- Un serveur [Ollama](https://ollama.com/) local fonctionnel.

### Démarrage rapide

1. **Cloner le dépôt**
   ```bash
   git clone https://github.com/ChtiAxel/appli_intelligente.git
   cd appli_intelligente
   ```

2. **Démarrer les conteneurs (Base de données & Application Web)**
   ```bash
   docker-compose up -d --build
   ```

3. **Accéder à l'application**
   Ouvrez votre navigateur internet sur : [http://localhost:7860](http://localhost:7860)

---

## 📚 Documentation & Liens utiles

- 🌐 **[Documentation Utilisateur complète (MkDocs en ligne)](https://chtiaxel.github.io/appli_intelligente/)**
- 📋 **[Gestion de Projet Trello](https://trello.com/b/y17crC4E/saeappint)**
- 🎨 **[Maquettes & UI/UX Figma](https://www.figma.com/design/cfKw4rfIQzc63ogoopWKc4/AppliIntelligent)**

---

## 👥 Équipe de Développement

- **Axel NAVE**
- **Raphaël DEROO**
- **Rémy RAMPELBERGHE**
- **Noa GAILLARD**

--- 

## ⏳ Développement en cours

### V1