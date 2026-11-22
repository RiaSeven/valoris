# 📈 Valoris — Screener Boursier & Macro-Économique (V2)

**Valoris** est une application d'analyse fondamentale autonome et automatisée. Elle permet de détecter les actions sous-évaluées (modèle DCF) et de suivre les grandes tendances macroéconomiques (bourses US, Europe, Japon, Corée du Sud, indices et matières premières).

---

## 🔬 Critères de Sélection & Système de Notation

### 1. Univers d'investissement

- **Actions éligibles** : Entreprises cotées aux USA, en Europe, au Japon (`.T`) et en Corée du Sud (`.KS`).
- **Filtre de taille** : Capitalisation boursière **> 1,0 milliard d'Euros** (convertie automatiquement selon les taux `EURUSD`, `EURJPY` et `EURKRW`).
- **Macroéconomie** : Suivi des indices majeurs (`^FCHI`, `^GSPC`, `^N225`, `^KS11`), des futures (`ES=F`, `NQ=F`) et des matières premières (`GC=F` Or, `BZ=F` Brent, `CL=F` WTI).

### 2. Calcul de la Décote (Discount)

La valeur intrinsèque ($V_i$) est calculée selon le modèle **Discounted Cash Flow (DCF)** à 2 phases :

- **Taux d'actualisation ($r$)** : 8,5% (WACC standard).
- **Taux de croissance perpétuel ($g_n$)** : 2,0%.
- **Décote (\%)** : $\frac{\text{Cours actuel} - V_i}{V_i} \times 100$.
- *Une sous-évaluation d'au moins 20% est ciblée.*

### 3. Grille du Score de Santé (Note sur 10)

| Critère | Indicateur | Condition de validation | Points |
| --- | --- | --- | --- |
| **Piotroski F-Score** | ROA / Cash-Flow / Marges | 4 sous-critères (ROA positif, Cash opérationnel > Résultat net, expansion des marges, rotation des actifs) | 4,0 pts |
| **Solvabilité** | Altman Z-Score | Score Z > 2,99 (+2 pts) ou entre 1,81 et 2,99 (+1 pt) | 2,0 pts |
| **Endettement** | Dette Nette / EBITDA | Dette/EBITDA < 2,5x ou Dette/Kapital < 0,8 | 1,0 pt |
| **Rentabilité** | ROIC & Marge FCF | ROIC > 12% (+1 pt) et Marge FCF > 10% (+1 pt) | 2,0 pts |
| **Croissance** | CAGR Chiffre d'affaires | Croissance des ventes sur 3 ans > 5% | 1,0 pt |
| **TOTAL** |     |     | **10,0 pts** |

---

## 🛠️ Architecture V2 & Déploiement

```
valoris/
├── .github/
│   └── workflows/
│       └── update.yml          # Automation GitHub Actions (2 exécutions/jour)
├── fetch_and_score.py          # Script Python V2 (DCF, multi-devises, Macro)
├── index.html                  # Dashboard web V2 (Screener + Onglet Macro)
├── requirements.txt            # Dependances (yfinance, pandas, numpy)
├── data.json                   # Données générées automatiquement
└── history.json                # Historique des performances
```

### Déclenchement automatique (`update.yml`)

Le workflow s'exécute automatiquement **deux fois par jour** du lundi au vendredi :

- **08:30 UTC** (clôture des bourses asiatiques).
- **20:30 UTC** (clôture des bourses occidentales).
