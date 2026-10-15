"""Étape 1 de LibrIA : collecter des livres sur Google Books et archiver les réponses brutes.

Pour chaque mot-clé de `mots_cles.txt`, le script interroge Google Books page par page
et enregistre chaque réponse telle quelle dans `data/raw/<mot-cle>/page_0000.json`.
On ne transforme rien ici : le nettoyage se fera à l'étape 2, à partir de cette archive.

Si une page est déjà enregistrée, elle est sautée : on peut donc arrêter le script
(Ctrl + C) et le relancer plus tard, il reprend là où il s'était arrêté.

Utilisation (depuis le dossier du projet) :
    python pipeline/collecte_google_books.py
    python pipeline/collecte_google_books.py --mots "Fantasy" "Polar"
    python pipeline/collecte_google_books.py --max-pages 2
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests
from dotenv import load_dotenv

URL_API = "https://www.googleapis.com/books/v1/volumes"
RESULTATS_PAR_PAGE = 40  # maximum autorisé par Google Books
PAUSE_ENTRE_REQUETES = 1.0  # secondes, pour rester poli avec l'API

DOSSIER_PROJET = Path(__file__).resolve().parent.parent
DOSSIER_RAW = DOSSIER_PROJET / "data" / "raw"
FICHIER_MOTS_CLES = Path(__file__).resolve().parent / "mots_cles.txt"


def nom_de_dossier(mot_cle):
    """Transforme 'Littérature d'enfance' en 'litterature-d-enfance' (sans accents ni espaces)."""
    texte = unicodedata.normalize("NFKD", mot_cle).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-")


def lire_mots_cles():
    lignes = FICHIER_MOTS_CLES.read_text(encoding="utf-8").splitlines()
    return [ligne.strip() for ligne in lignes if ligne.strip() and not ligne.startswith("#")]


def telecharger_page(mot_cle, index_depart, cle_api):
    """Demande une page de résultats à Google Books. Réessaie si l'API demande de ralentir."""
    parametres = {
        "q": mot_cle,
        "startIndex": index_depart,
        "maxResults": RESULTATS_PAR_PAGE,
        "langRestrict": "fr",
        "printType": "books",
    }
    if cle_api:
        parametres["key"] = cle_api

    for essai in range(5):
        reponse = requests.get(URL_API, params=parametres, timeout=30)
        if reponse.status_code == 429:
            if "per day" in reponse.text.lower():
                sys.exit("Quota du jour atteint chez Google Books. Relance le script demain, il reprendra où il s'est arrêté.")
            attente = 2 ** (essai + 1)
            print(f"  Google demande de ralentir, pause de {attente} s...")
            time.sleep(attente)
            continue
        reponse.raise_for_status()
        return reponse.json()
    raise RuntimeError("Google Books refuse toujours la requête après 5 essais.")


def collecter(mot_cle, cle_api, max_pages):
    dossier = DOSSIER_RAW / nom_de_dossier(mot_cle)
    dossier.mkdir(parents=True, exist_ok=True)
    print(f"\n== {mot_cle}")

    for numero_page in range(max_pages):
        fichier = dossier / f"page_{numero_page:04d}.json"
        if fichier.exists():
            donnees = json.loads(fichier.read_text(encoding="utf-8"))
        else:
            donnees = telecharger_page(mot_cle, numero_page * RESULTATS_PAR_PAGE, cle_api)
            donnees["_libria"] = {"mot_cle": mot_cle, "page": numero_page, "date": time.strftime("%Y-%m-%d")}
            fichier.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
            time.sleep(PAUSE_ENTRE_REQUETES)

        nb_livres = len(donnees.get("items", []))
        print(f"  page {numero_page} : {nb_livres} livres")
        if nb_livres < RESULTATS_PAR_PAGE:
            break  # plus de résultats pour ce mot-clé


def main():
    parser = argparse.ArgumentParser(description="Collecte des livres Google Books (archive brute).")
    parser.add_argument("--mots", nargs="+", help="mots-clés à utiliser (par défaut : tout mots_cles.txt)")
    parser.add_argument("--max-pages", type=int, default=25, help="nombre de pages de 40 livres par mot-clé (25 par défaut)")
    args = parser.parse_args()

    load_dotenv(DOSSIER_PROJET / ".env")
    cle_api = os.getenv("GOOGLE_BOOKS_API_KEY", "").strip()
    if not cle_api:
        print("Attention : pas de clé API dans .env, Google risque de refuser les requêtes (voir README).")

    mots_cles = args.mots or lire_mots_cles()
    print(f"{len(mots_cles)} mot(s)-clé(s) à traiter, archive dans {DOSSIER_RAW}")
    for mot_cle in mots_cles:
        collecter(mot_cle, cle_api, args.max_pages)
    print("\nCollecte terminée.")


if __name__ == "__main__":
    main()
