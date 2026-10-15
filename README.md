# LibrIA

Application web qui suggère des livres parus en français, à partir de la ressemblance de leur contenu.
Chaque utilisateur peut créer un compte et ranger ses livres : **Lu**, **En cours**, **À lire**.

Le projet reprend les idées de l'ancien dépôt [Asuura666/Libria](https://github.com/Asuura666/Libria) dans une structure propre.

## Avancement

| Étape | Contenu | État |
|---|---|---|
| 1 | Collecte Google Books et archive brute (`data/raw/`) | ✅ script prêt |
| 2 | Nettoyage : français uniquement, sans doublons (`data/clean/livres.csv`) | ✅ script prêt |
| 3 | Couvertures de la première édition (Open Library + Google Books) | à faire |
| 4 | Moteur de recommandation (similarité des résumés) | à faire |
| 5 | Site web Django : comptes, fiches livres, bibliothèque perso | à faire |
| 6 | Mise en ligne gratuite | plus tard |

## Installation sous Windows (une seule fois)

1. Installe **Python 3.12** depuis [python.org](https://www.python.org/downloads/). Pendant l'installation, coche **« Add python.exe to PATH »**.
2. Installe **Git** depuis [git-scm.com](https://git-scm.com/).
3. Dans VS Code, installe l'extension **Python** (de Microsoft).
4. Ouvre un terminal dans VS Code (menu *Terminal > Nouveau terminal*) et tape :

```powershell
git clone https://github.com/Cyber-Elu/LibrIA.git
cd LibrIA
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell refuse la commande `Activate.ps1`, tape d'abord
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` puis réessaie.

À chaque nouvelle session, il suffit de refaire `.venv\Scripts\Activate.ps1` (le début de la ligne affiche alors `(.venv)`).

## Obtenir une clé Google Books (gratuite)

Sans clé, Google refuse souvent les requêtes.

1. Va sur [console.cloud.google.com](https://console.cloud.google.com/) et connecte-toi avec un compte Google.
2. Crée un projet (par exemple « LibrIA »).
3. Menu *API et services > Bibliothèque*, cherche **Books API** et clique sur **Activer**.
4. Menu *API et services > Identifiants > Créer des identifiants > Clé API*. Copie la clé.
5. Dans le dossier du projet, copie le fichier `.env.example` en `.env` et colle ta clé après `GOOGLE_BOOKS_API_KEY=`.

Le fichier `.env` reste sur ton PC : il est ignoré par Git, ta clé ne part pas sur GitHub.

## Étape 1 : collecter les livres

```powershell
# Petit essai : 2 pages pour un seul mot-clé
python pipeline/collecte_google_books.py --mots "Fantasy" --max-pages 2

# Collecte complète (tous les mots-clés de pipeline/mots_cles.txt)
python pipeline/collecte_google_books.py
```

Les réponses de Google sont archivées telles quelles dans `data/raw/<mot-cle>/page_XXXX.json`.
Le script peut être arrêté avec `Ctrl + C` et relancé : il reprend là où il s'était arrêté.
Le quota gratuit est d'environ 1 000 requêtes par jour, la collecte complète prend donc plusieurs jours.

Pour ajouter des thèmes, ajoute une ligne dans `pipeline/mots_cles.txt`.

## Étape 2 : nettoyer les données

Une fois quelques pages collectées (même une petite partie suffit pour essayer) :

```powershell
python pipeline/nettoyage.py
```

Le script lit l'archive `data/raw/` sans la modifier et crée `data/clean/livres.csv`, avec un livre par ligne :

- uniquement les livres en français, avec un titre, un auteur et un vrai résumé ;
- résumés débarrassés des balises HTML ;
- les éditions d'un même livre (même titre et même auteur) regroupées en une seule ligne,
  avec la date de parution la plus ancienne et tous les ISBN.

Le fichier s'ouvre directement dans Excel (séparateur `;`). Le script affiche aussi combien de livres ont été écartés et pourquoi.
On peut le relancer à chaque fois que la collecte avance.

Pour vérifier que le nettoyage fonctionne, sans rien télécharger :

```powershell
python -m unittest discover tests
```

## Organisation des dossiers

```
LibrIA/
├── pipeline/            scripts de traitement des données
│   ├── collecte_google_books.py   étape 1 : collecte
│   ├── nettoyage.py               étape 2 : nettoyage
│   └── mots_cles.txt
├── tests/               vérifications automatiques et petites données d'exemple
├── data/
│   ├── raw/             archive brute de Google Books (pas envoyée sur GitHub)
│   └── clean/           données nettoyées (pas envoyées sur GitHub)
├── requirements.txt     bibliothèques Python nécessaires
└── .env.example         modèle du fichier de configuration
```
