"""Vérifie le choix des couvertures avec des réponses Open Library simulées (aucun accès Internet).

Lancer depuis le dossier du projet :
    python -m unittest discover tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))

import couvertures  # noqa: E402

ETRANGER = {
    "id_livre": "ETR1972", "titre": "L'étranger", "auteurs": "Camus, Albert", "annee": "1972",
    "isbn": "9782070360000 | 9782070360024", "couverture_google": "https://books.google.com/etranger.jpg",
}
INCONNU = {
    "id_livre": "INC", "titre": "Livre inconnu", "auteurs": "Personne", "annee": "2020",
    "isbn": "", "couverture_google": "https://books.google.com/inconnu.jpg",
}

EDITIONS_ETRANGER = {"size": 4, "entries": [
    {"key": "/books/OL1M", "publish_date": "1942", "languages": [{"key": "/languages/fre"}], "covers": [-1]},
    {"key": "/books/OL2M", "publish_date": "Mai 1957", "languages": [{"key": "/languages/fre"}], "covers": [222]},
    {"key": "/books/OL3M", "publish_date": "1946", "languages": [{"key": "/languages/eng"}], "covers": [333]},
    {"key": "/books/OL4M", "publish_date": "2005", "languages": [{"key": "/languages/fre"}], "covers": [444]},
]}


def faux_open_library(url, parametres=None):
    """Imite Open Library : seul le 2e ISBN de L'étranger est connu."""
    parametres = parametres or {}
    if url == couvertures.URL_RECHERCHE:
        if parametres.get("isbn") == "9782070360024":
            return {"docs": [{"key": "/works/OL1W"}]}
        if parametres.get("title") == "Livre inconnu":
            return {"docs": [{"key": "/works/MAUVAIS", "title": "Livre inconnu", "author_name": ["Quelqu'un d'autre"]}]}
        return {"docs": []}
    if url == couvertures.URL_EDITIONS.format(oeuvre="/works/OL1W"):
        return EDITIONS_ETRANGER
    raise AssertionError(f"URL inattendue : {url}")


class TestCouvertures(unittest.TestCase):
    def setUp(self):
        self.cache = Path(tempfile.mkdtemp())

    def test_premiere_edition_francaise_avec_couverture(self):
        etranger, inconnu = couvertures.traiter([ETRANGER, INCONNU], faux_open_library, self.cache)
        # 1942 n'a pas de couverture, 1946 est en anglais : on garde 1957.
        self.assertEqual(etranger["source"], "openlibrary")
        self.assertEqual(etranger["annee_edition"], 1957)
        self.assertEqual(etranger["edition_openlibrary"], "/books/OL2M")
        self.assertEqual(etranger["url_couverture"], "https://covers.openlibrary.org/b/id/222-L.jpg")
        # Le résultat de recherche n'a pas le bon auteur : on garde la couverture Google.
        self.assertEqual(inconnu["source"], "google")
        self.assertEqual(inconnu["oeuvre_openlibrary"], "")
        self.assertEqual(inconnu["url_couverture"], "https://books.google.com/inconnu.jpg")

    def test_reprise_sans_nouvelle_requete(self):
        couvertures.traiter([ETRANGER], faux_open_library, self.cache)

        def interdit(url, parametres=None):
            raise AssertionError("Open Library ne devrait plus être interrogé")

        (resultat,) = couvertures.traiter([ETRANGER], interdit, self.cache)
        self.assertEqual(resultat["annee_edition"], 1957)

    def test_annee(self):
        self.assertEqual(couvertures.annee("March 1942"), 1942)
        self.assertEqual(couvertures.annee("12/03/1957"), 1957)
        self.assertIsNone(couvertures.annee("sans date"))


if __name__ == "__main__":
    unittest.main()
