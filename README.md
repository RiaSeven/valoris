# 🚀 Valoris V3 — Quantitative Market Engine

![GitHub Actions Workflow Status](https://img.shields.io/badge/GitHub%20Actions-Automated-emerald?style=for-the-badge&logo=githubactions)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Frontend](https://img.shields.io/badge/Interface-Tailwind%20%2B%20HTML5-06B6D4?style=for-the-badge&logo=tailwindcss)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

**Valoris V3** est une plateforme d'analyse quantitative boursière multi-marchés conçue pour scanner, filtrer et évaluer en continu les opportunités d'investissement sur les marchés internationaux (**Session Asie Matin** et **Session Occident Soir**).

---

## ✨ Fonctionnalités Clés

- 🌏 **Analyse Bi-Quotidienne Synchronisée** :
  - **Session Asie (Matin)** : Analyse ciblée sur les bourses de Tokyo (Nikkei 225), Hong Kong (Hang Seng) et Taïwan (TWSE).
  - **Session Occident (Soir)** : Analyse des marchés américains (S&P 500, Nasdaq) et européens (EuroStoxx 50, CAC 40).
- 📊 **Scoring Multi-Facteurs (0 à 100 pts)** :
  - Valorisation (P/E relatif, P/B, FCF Yield)
  - Momentum & RSI (Divergences, Trend Alignment)
  - Santé Financière & Rentabilité (ROE, Debt/Equity)
- 🖥️ **Page d'Accueil Sublime avec Effet "Waouh"** :
  - Visualisation des données sous forme de terminal financier interactif.
  - Fond animé réactif, widgets de statuts de marché en direct.
  - Screener dynamique avec filtres instantanés par recherche, secteur et session.
- ⚙️ **Automation Serverless** : Exécution automatique des pipelines de données via GitHub Actions (`update.yml`).

---

## 🛠️ Architecture du Projet

```text
valoris/
├── index.html                # Interface Web UI V3 (Hero Landing + Screener)
├── README.md                 # Documentation du projet
├── data/                     # Fichiers de données générés par les pipelines
│   ├── asia_session.json     # Résultats d'analyse Asie
│   └── west_session.json     # Résultats d'analyse Occident
└── .github/
    └── workflows/
        └── update.yml        # Automation CI/CD GitHub Actions (Run workflow)
```

---

## ⚡ Exécution Manuelle via GitHub Actions

Pour déclencher le rebalancement et la mise à jour des données du Screener :

1. Naviguez dans l'onglet **Actions** de votre dépôt GitHub.
2. Dans le menu latéral de gauche, sélectionnez le workflow :  
   `Mise à jour Valoris V3 (Asie matin & Occident soir)` *(ou `Mise à jour quotidienne Valoris`)*.
3. Cliquez sur le bouton dropdown **`Run workflow ▾`** situé en haut à droite de la liste des exécutions.
4. Sélectionnez la branche **`main`**, choisissez la session souhaitée (`all`, `asia` ou `west`), puis validez avec le bouton vert **Run workflow**.

---

## 💻 Visualisation Locale

Pour exécuter l'interface web localement sans installation lourde :

```bash
# Clonez le dépôt
git clone https://github.com/RiaSeven/valoris.git
cd valoris

# Ouvrez simplement index.html dans votre navigateur
# Ou lancez un serveur local rapide avec Python :
python -m http.server 8000
```

Rendez-vous ensuite sur `http://localhost:8000` pour profiter de l'expérience interactive.

---

## 🛡️ Licence & Contribution

Projet distribué sous licence MIT. Les contributions pour étendre les facteurs quantitatifs ou ajouter de nouveaux indices boursiers sont les bienvenues !