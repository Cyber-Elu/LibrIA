"""Étape 3 de LibrIA : trouver la couverture de la première édition française de chaque livre.

Google Books ne sait pas quelle édition est la première. Open Library (gratuit, sans clé)
regroupe toutes les éditions d'une même œuvre : pour chaque livre de `data/clean/livres.csv`,
on retrouve l'œuvre sur Open Library, on regarde ses éditions en français qui ont une couverture
et on garde la plus ancienne. Si on ne trouve rien, on garde la couverture de Google Books.

Les réponses d'Open Library sont archivées dans `data/raw/openlibrary/` : si le script s'arrête
(Ctrl + C), il reprend là où il en était, sans redemander ce qu'il connaît déjà.

Le résultat est `data/clean/couvertures.csv` (une ligne par livre).

Utilisation (depuis le dossier du projet) :
    python pipeline/couvertures.py
    python pipeline/couvertures.py --max-livres 20     # petit essai
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nettoyage import FICHIER_SORTIE as FICHIER_LIVRES  # noqa: E402
from nettoyage import SEPARATEUR_LISTE, cle_auteur, normaliser  # noqa: E402

DOSSIER_PROJET = Path(__file__).resolve().parent.parent
DOSSIER_CACHE = DOSSIER_PROJET / "data" / "raw" / "openlibrary"
FICHIER_SORTIE = DOSSIER_PROJET / "data" / "clean" / "couvertures.csv"

URL_RECHERCHE = "https://openlibrary.org/search.json"
URL_EDITIONS = "https://openlibrary.org{oeuvre}/editions.json"
URL_COUVERTURE = "https://covers.openlibrary.org/b/id/{id}-L.jpg"
LANGUE_FRANCAIS = "/languages/fre"
PAUSE_ENTRE_REQUETES = 1.0  # secondes : Open Library demande de ne pas aller trop vite
EN_TETES = {"User-Agent": "LibrIA/0.1 (projet personnel de suggestion de livres)"}

COLONNES = ["id_livre", "source", "url_couverture", "annee_edition", "oeuvre_openlibrary", "edition_openlibrary"]


# --- Accès à Open Library -------------------------------------------------------------------

def telecharger_json(url, parametres=None):
    """Demande une page à Open Library. Réessaie quelques fois si le site est lent ou surchargé."""
    for essai in range(4):
        try:
            reponse = requests.get(url, params=parametres, headers=EN_TETES, timeout=30)
            if reponse.status_code == 404:
                return {}
            if reponse.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"code {reponse.status_code}")
            reponse.raise_for_status()
            time.sleep(PAUSE_ENTRE_REQUETES)
            return reponse.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as erreur:
            attente = 5 * (essai + 1)
            print(f"  Open Library ne répond pas ({erreur}), nouvel essai dans {attente} s...")
            time.sleep(attente)
    raise RuntimeError("Open Library ne répond plus. Relance le script plus tard, il reprendra où il en était.")


def meme_livre(document, titre, auteurs):
    """Vérifie qu'un résultat de recherche Open Library correspond bien à notre livre."""
    if normaliser(document.get("title")) != normaliser(titre):
        return False
    nos_auteurs = {cle_auteur(a) for a in auteurs.split(SEPARATEUR_LISTE) if a}
    leurs_auteurs = {cle_auteur(a) for a in document.get("author_name", [])}
    return bool(nos_auteurs & leurs_auteurs)


def trouver_oeuvre(livre, obtenir_json):
    """Renvoie la clé de l'œuvre sur Open Library (ex. '/works/OL45804W'), ou '' si introuvable."""
    # 1) Par ISBN : le plus fiable.
    for isbn in filter(None, livre["isbn"].split(SEPARATEUR_LISTE)):
        resultat = obtenir_json(URL_RECHERCHE, {"isbn": isbn, "fields": "key", "limit": 1})
        documents = resultat.get("docs", [])
        if documents:
            return documents[0]["key"]
    # 2) Sinon par titre + auteur, en vérifiant que le titre et l'auteur correspondent vraiment.
    premier_auteur = livre["auteurs"].split(SEPARATEUR_LISTE)[0]
    resultat = obtenir_json(URL_RECHERCHE, {
        "title": livre["titre"], "author": premier_auteur,
        "fields": "key,title,author_name", "limit": 10,
    })
    for document in resultat.get("docs", []):
        if meme_livre(document, livre["titre"], livre["auteurs"]):
            return document["key"]
    return ""


def lire_editions(oeuvre, obtenir_json):
    """Renvoie toutes les éditions connues d'une œuvre (Open Library les donne par paquets)."""
    editions = []
    url = URL_EDITIONS.format(oeuvre=oeuvre)
    parametres = {"limit": 100, "offset": 0}
    while True:
        page = obtenir_json(url, parametres)
        entrees = page.get("entries", [])
        editions.extend(entrees)
        if len(entrees) < parametres["limit"] or len(editions) >= page.get("size", 0) or len(editions) >= 1000:
            return editions
        parametres = {"limit": 100, "offset": len(editions)}


def infos_openlibrary(livre, obtenir_json, dossier_cache):
    """Œuvre + éditions d'un livre, lues dans l'archive si on les a déjà demandées."""
    fichier = dossier_cache / f"{livre['id_livre']}.json"
    if fichier.exists():
        return json.loads(fichier.read_text(encoding="utf-8"))
    oeuvre = trouver_oeuvre(livre, obtenir_json)
    infos = {"oeuvre": oeuvre, "editions": lire_editions(oeuvre, obtenir_json) if oeuvre else []}
    dossier_cache.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps(infos, ensure_ascii=False), encoding="utf-8")
    return infos


# --- Choix de la couverture -----------------------------------------------------------------

def annee(texte):
    """'March 1942', '1942', '12/03/1942' -> 1942 ; None si pas d'année."""
    trouve = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", texte or "")
    return int(trouve.group(1)) if trouve else None


def premiere_edition_francaise(editions):
    """Parmi les éditions en français qui ont une couverture et une date, renvoie la plus ancienne."""
    candidates = []
    for edition in editions:
        langues = {langue.get("key") for langue in edition.get("languages", [])}
        couvertures = [c for c in edition.get("covers", []) if c and c > 0]
        an = annee(edition.get("publish_date"))
        if LANGUE_FRANCAIS in langues and couvertures and an:
            candidates.append((an, edition["key"], couvertures[0]))
    return min(candidates) if candidates else None


def choisir_couverture(livre, infos):
    """Couverture de la première édition française sur Open Library, sinon celle de Google Books."""
    choix = premiere_edition_francaise(infos["editions"])
    if choix:
        an, edition, id_couverture = choix
        return {
            "id_livre": livre["id_livre"], "source": "openlibrary",
            "url_couverture": URL_COUVERTURE.format(id=id_couverture), "annee_edition": an,
            "oeuvre_openlibrary": infos["oeuvre"], "edition_openlibrary": edition,
        }
    return {
        "id_livre": livre["id_livre"],
        "source": "google" if livre["couverture_google"] else "aucune",
        "url_couverture": livre["couverture_google"], "annee_edition": livre["annee"],
        "oeuvre_openlibrary": infos["oeuvre"], "edition_openlibrary": "",
    }


# --- Programme principal --------------------------------------------------------------------

def lire_livres(fichier):
    with fichier.open(encoding="utf-8-sig", newline="") as entree:
        return list(csv.DictReader(entree, delimiter=";"))


def ecrire_csv(lignes, fichier):
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with fichier.open("w", encoding="utf-8-sig", newline="") as sortie:
        ecrivain = csv.DictWriter(sortie, fieldnames=COLONNES, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


def traiter(livres, obtenir_json=telecharger_json, dossier_cache=DOSSIER_CACHE):
    resultats = []
    for numero, livre in enumerate(livres, start=1):
        infos = infos_openlibrary(livre, obtenir_json, dossier_cache)
        resultat = choisir_couverture(livre, infos)
        resultats.append(resultat)
        print(f"  [{numero}/{len(livres)}] {livre['titre'][:50]} : {resultat['source']}")
    return resultats


def main():
    parser = argparse.ArgumentParser(description="Couvertures de la première édition française.")
    parser.add_argument("--livres", type=Path, default=FICHIER_LIVRES, help="CSV créé par l'étape 2")
    parser.add_argument("--sortie", type=Path, default=FICHIER_SORTIE, help="fichier CSV à créer")
    parser.add_argument("--max-livres", type=int, help="ne traiter que les N premiers livres (pour essayer)")
    args = parser.parse_args()

    if not args.livres.exists():
        sys.exit(f"Fichier {args.livres} introuvable. Lance d'abord l'étape 2 (nettoyage.py).")
    livres = lire_livres(args.livres)[: args.max_livres]
    print(f"{len(livres)} livres à traiter (archive Open Library dans {DOSSIER_CACHE})")

    resultats = []
    try:
        resultats = traiter(livres)
    except KeyboardInterrupt:
        sys.exit("\nArrêt demandé. Relance le script : il reprendra où il en était.")

    ecrire_csv(resultats, args.sortie)
    nb_ol = sum(r["source"] == "openlibrary" for r in resultats)
    nb_google = sum(r["source"] == "google" for r in resultats)
    print(f"\n{nb_ol} couvertures de première édition (Open Library), {nb_google} de Google Books, "
          f"{len(resultats) - nb_ol - nb_google} sans couverture. Résultat dans {args.sortie}")


if __name__ == "__main__":
    main()
