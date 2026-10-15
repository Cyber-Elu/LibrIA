"""Étape 2 de LibrIA : nettoyer l'archive brute de Google Books.

Le script lit tous les fichiers `data/raw/<mot-cle>/page_XXXX.json` créés par l'étape 1
et produit un tableau propre `data/clean/livres.csv`, avec un livre par ligne :

- on ne garde que les livres en français (`language` = "fr") ;
- on enlève les livres sans titre, sans auteur ou sans vrai résumé ;
- on nettoie les résumés (balises HTML, espaces en trop) ;
- on regroupe les éditions d'un même livre (même titre + même auteur) en une seule ligne,
  en gardant la date de parution la plus ancienne et tous les ISBN.

L'archive brute n'est jamais modifiée : on peut relancer ce script autant de fois qu'on veut.

Utilisation (depuis le dossier du projet) :
    python pipeline/nettoyage.py
"""

import argparse
import csv
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

DOSSIER_PROJET = Path(__file__).resolve().parent.parent
DOSSIER_RAW = DOSSIER_PROJET / "data" / "raw"
FICHIER_SORTIE = DOSSIER_PROJET / "data" / "clean" / "livres.csv"

LONGUEUR_MIN_RESUME = 80  # en caractères : en dessous, le résumé est trop court pour comparer des livres
SEPARATEUR_LISTE = " | "  # pour ranger plusieurs valeurs (auteurs, ISBN...) dans une seule case

COLONNES = [
    "id_livre", "titre", "sous_titre", "auteurs", "editeur", "date_parution", "annee",
    "description", "categories", "mots_cles", "nb_pages", "isbn", "ids_google",
    "couverture_google", "nb_editions",
]


# --- Petits outils sur le texte -------------------------------------------------------------

def sans_accents(texte):
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c))


def normaliser(texte):
    """'L'Étranger !' -> 'l etranger' : sert à comparer deux titres sans se soucier de la forme."""
    texte = sans_accents(texte or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", texte).strip()


def cle_auteur(auteur):
    """Garde les mots de plus d'une lettre, triés : 'Camus, Albert' et 'Albert Camus' donnent la même clé."""
    mots = [mot for mot in normaliser(auteur).split() if len(mot) > 1]
    return " ".join(sorted(mots))


def nettoyer_resume(texte):
    """Enlève les balises HTML (<p>, <br>, <b>...) et les espaces en trop."""
    texte = re.sub(r"<br\s*/?>|</p>", " ", texte or "", flags=re.IGNORECASE)
    texte = re.sub(r"<[^>]+>", "", texte)
    texte = html.unescape(texte)
    return re.sub(r"\s+", " ", texte).strip()


def lien_image_propre(lien):
    """Passe le lien en https et enlève l'effet « page cornée » que Google ajoute parfois."""
    if not lien:
        return ""
    lien = lien.replace("http://", "https://", 1)
    return lien.replace("&edge=curl", "")


# --- Lecture de l'archive -------------------------------------------------------------------

def lire_archive(dossier_raw):
    """Renvoie la liste des livres bruts trouvés dans l'archive, avec le mot-clé qui les a trouvés."""
    livres = []
    for fichier in sorted(dossier_raw.glob("*/page_*.json")):
        donnees = json.loads(fichier.read_text(encoding="utf-8"))
        mot_cle = donnees.get("_libria", {}).get("mot_cle", fichier.parent.name)
        for item in donnees.get("items", []):
            livres.append((item, mot_cle))
    return livres


def extraire_edition(item, mot_cle):
    """Garde uniquement les informations utiles d'une réponse Google Books."""
    info = item.get("volumeInfo", {})
    isbn = [
        identifiant["identifier"]
        for identifiant in info.get("industryIdentifiers", [])
        if identifiant.get("type") in ("ISBN_13", "ISBN_10")
    ]
    images = info.get("imageLinks", {})
    return {
        "id_google": item.get("id", ""),
        "titre": (info.get("title") or "").strip(),
        "sous_titre": (info.get("subtitle") or "").strip(),
        "auteurs": [a.strip() for a in info.get("authors", []) if a.strip()],
        "editeur": (info.get("publisher") or "").strip(),
        "date_parution": (info.get("publishedDate") or "").strip(),
        "description": nettoyer_resume(info.get("description")),
        "categories": info.get("categories", []),
        "nb_pages": info.get("pageCount") or "",
        "langue": info.get("language", ""),
        "isbn": isbn,
        "couverture": lien_image_propre(images.get("thumbnail") or images.get("smallThumbnail")),
        "mot_cle": mot_cle,
    }


def raison_de_rejet(edition):
    """Renvoie pourquoi une édition est écartée, ou None si on la garde."""
    if edition["langue"] != "fr":
        return "pas en français"
    if not edition["titre"]:
        return "sans titre"
    if not edition["auteurs"]:
        return "sans auteur"
    if len(edition["description"]) < LONGUEUR_MIN_RESUME:
        return "résumé absent ou trop court"
    return None


# --- Regroupement des éditions --------------------------------------------------------------

def cle_livre(edition):
    return (normaliser(edition["titre"]), cle_auteur(edition["auteurs"][0]))


def ordre_date(edition):
    """Les éditions sans date passent en dernier ; '2005' et '2005-03-12' se comparent bien comme texte."""
    return edition["date_parution"] or "9999"


def sans_doublons(valeurs):
    vues = []
    for valeur in valeurs:
        if valeur and valeur not in vues:
            vues.append(valeur)
    return vues


def fusionner(editions):
    """Fait une seule ligne à partir de toutes les éditions d'un même livre."""
    editions = sorted(editions, key=ordre_date)
    plus_ancienne = editions[0]
    plus_long_resume = max(editions, key=lambda e: len(e["description"]))
    avec_image = [e for e in editions if e["couverture"]]
    date = plus_ancienne["date_parution"]
    return {
        "id_livre": plus_ancienne["id_google"],
        "titre": plus_ancienne["titre"],
        "sous_titre": plus_ancienne["sous_titre"] or plus_long_resume["sous_titre"],
        "auteurs": SEPARATEUR_LISTE.join(plus_ancienne["auteurs"]),
        "editeur": plus_ancienne["editeur"],
        "date_parution": date,
        "annee": date[:4] if date[:4].isdigit() else "",
        "description": plus_long_resume["description"],
        "categories": SEPARATEUR_LISTE.join(sans_doublons(c for e in editions for c in e["categories"])),
        "mots_cles": SEPARATEUR_LISTE.join(sans_doublons(e["mot_cle"] for e in editions)),
        "nb_pages": max((e["nb_pages"] for e in editions if e["nb_pages"]), default=""),
        "isbn": SEPARATEUR_LISTE.join(sans_doublons(i for e in editions for i in e["isbn"])),
        "ids_google": SEPARATEUR_LISTE.join(sans_doublons(e["id_google"] for e in editions)),
        # Couverture provisoire : l'étape 3 cherchera celle de la première édition.
        "couverture_google": avec_image[0]["couverture"] if avec_image else "",
        "nb_editions": len(sans_doublons(e["id_google"] for e in editions)),
    }


def nettoyer(dossier_raw):
    """Renvoie (livres propres, compteur des rejets, nombre d'éditions lues)."""
    brutes = lire_archive(dossier_raw)
    rejets = Counter()
    groupes = {}
    for item, mot_cle in brutes:
        edition = extraire_edition(item, mot_cle)
        raison = raison_de_rejet(edition)
        if raison:
            rejets[raison] += 1
            continue
        groupes.setdefault(cle_livre(edition), []).append(edition)
    livres = [fusionner(editions) for editions in groupes.values()]
    livres.sort(key=lambda livre: normaliser(livre["titre"]))
    return livres, rejets, len(brutes)


def ecrire_csv(livres, fichier):
    """CSV avec « ; » et encodage utf-8-sig : il s'ouvre directement et proprement dans Excel."""
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with fichier.open("w", encoding="utf-8-sig", newline="") as sortie:
        ecrivain = csv.DictWriter(sortie, fieldnames=COLONNES, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(livres)


def main():
    parser = argparse.ArgumentParser(description="Nettoyage de l'archive Google Books.")
    parser.add_argument("--raw", type=Path, default=DOSSIER_RAW, help="dossier de l'archive brute")
    parser.add_argument("--sortie", type=Path, default=FICHIER_SORTIE, help="fichier CSV à créer")
    args = parser.parse_args()

    livres, rejets, nb_lus = nettoyer(args.raw)
    if nb_lus == 0:
        print(f"Aucun livre trouvé dans {args.raw}. Lance d'abord l'étape 1 (collecte_google_books.py).")
        return

    ecrire_csv(livres, args.sortie)
    print(f"{nb_lus} résultats Google lus dans l'archive.")
    for raison, nombre in rejets.most_common():
        print(f"  - {nombre} écartés : {raison}")
    print(f"{len(livres)} livres différents gardés, enregistrés dans {args.sortie}")


if __name__ == "__main__":
    main()
