# LibrIA

Application web qui suggère des livres parus en français, à partir de la ressemblance de leur contenu.
Chaque utilisateur peut créer un compte et ranger ses livres : **Lu**, **En cours**, **À lire**.

Le projet reprend les idées de l'ancien dépôt [Asuura666/Libria](https://github.com/Asuura666/Libria) dans une structure propre.

## Avancement

| Étape | Contenu | État |
|---|---|---|
| 1 | Collecte Google Books et archive brute (`data/raw/`) | ✅ script prêt |
| 2 | Nettoyage : français uniquement, sans doublons (`data/clean/livres.csv`) | ✅ script prêt |
| 3 | Couvertures de la première édition (Open Library + Google Books) | ✅ script prêt |
| 4 | Moteur de recommandation (similarité des résumés) | ✅ script prêt |
| 5 | Site web Django : comptes, fiches livres, bibliothèque perso, suggestions | ✅ prêt |
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

## Étape 3 : trouver les couvertures de la première édition

```powershell
# Petit essai sur 20 livres
python pipeline/couvertures.py --max-livres 20

# Tous les livres de data/clean/livres.csv
python pipeline/couvertures.py
```

Google Books ne sait pas quelle édition est la première. Le script interroge donc
[Open Library](https://openlibrary.org) (gratuit, sans clé), qui regroupe toutes les éditions d'une même œuvre.
Pour chaque livre, il garde la couverture de **l'édition en français la plus ancienne** qui en a une.
S'il ne trouve rien, il garde la couverture de Google Books.

Le résultat est `data/clean/couvertures.csv` (colonne `source` : `openlibrary`, `google` ou `aucune`).
Les réponses d'Open Library sont archivées dans `data/raw/openlibrary/` : le script peut être arrêté avec `Ctrl + C`
et relancé, il reprend où il en était. Il fait une pause d'une seconde entre deux demandes, donc compter
environ 3 secondes par livre la première fois.

Ce n'est pas parfait : Open Library ne connaît pas tous les livres et ses dates sont parfois approximatives.

## Étape 4 : calculer les livres similaires

```powershell
python pipeline/recommandations.py
```

Pour chaque livre, un petit modèle d'intelligence artificielle gratuit
([sentence-transformers](https://www.sbert.net/), qui comprend le français) transforme le titre,
les catégories et le résumé en une « empreinte » : une liste de nombres qui résume le sens du texte.
Deux livres aux empreintes proches parlent de choses proches.

Le script garde les 20 livres les plus proches de chaque livre dans `data/clean/similaires.csv`
(colonne `score` : 1 = même sens, 0 = aucun rapport) et affiche un exemple pour vérifier à l'œil.

- La première fois, le modèle (≈ 500 Mo) est téléchargé automatiquement.
- Tout tourne sur ton PC, sans carte graphique : compter quelques minutes pour quelques milliers de livres.
- Les empreintes sont gardées dans `data/clean/empreintes.npy` : en relançant après une nouvelle collecte,
  seuls les nouveaux livres sont calculés.

## Étape 5 : lancer le site web

La première fois :

```powershell
python manage.py migrate              # crée la base de données (fichier db.sqlite3)
python manage.py importer_livres      # charge les livres préparés par les étapes 2, 3 et 4
python manage.py createsuperuser      # optionnel : un compte administrateur
```

Ensuite, à chaque fois :

```powershell
python manage.py runserver
```

Ouvre [http://127.0.0.1:8000](http://127.0.0.1:8000) dans ton navigateur. Le site s'arrête avec `Ctrl + C` dans le terminal.

Ce que propose le site :

- **Créer un compte**, se connecter et se déconnecter ;
- **Rechercher** un livre par titre ou auteur ;
- **Fiche livre** : couverture, résumé et livres qui lui ressemblent ;
- **Ma bibliothèque** : sur la fiche d'un livre, les boutons **Lu**, **En cours** et **À lire** le rangent dans ta bibliothèque ;
- **Pour toi** : des livres qui ressemblent à ceux que tu as lus ou que tu es en train de lire ;
- **Administration** sur [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) avec le compte créé par `createsuperuser`.

Après une nouvelle collecte, relance les étapes 2 à 4 puis `python manage.py importer_livres` :
les livres sont mis à jour et les bibliothèques des utilisateurs sont conservées.

## Vérifier que tout fonctionne

```powershell
python manage.py test
```

Lance toutes les vérifications automatiques (scripts de données et site), sans rien télécharger.

## Organisation des dossiers

```
LibrIA/
├── pipeline/            scripts de traitement des données
│   ├── collecte_google_books.py   étape 1 : collecte
│   ├── nettoyage.py               étape 2 : nettoyage
│   ├── couvertures.py             étape 3 : couvertures
│   ├── recommandations.py         étape 4 : livres similaires
│   └── mots_cles.txt
├── libria/              réglages du site Django
├── livres/              le site : pages, base de données, import des livres
│   ├── templates/       les pages HTML
│   └── static/          la feuille de style
├── manage.py            commandes du site (runserver, migrate, importer_livres…)
├── tests/               vérifications automatiques des scripts et petites données d'exemple
├── data/
│   ├── raw/             archive brute de Google Books (pas envoyée sur GitHub)
│   └── clean/           données nettoyées (pas envoyées sur GitHub)
├── requirements.txt     bibliothèques Python nécessaires
└── .env.example         modèle du fichier de configuration
```
