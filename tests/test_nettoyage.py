"""Vérifie le nettoyage sur un petit jeu de données d'exemple.

Lancer depuis le dossier du projet :
    python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

DOSSIER_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER_TESTS.parent / "pipeline"))

import nettoyage  # noqa: E402


class TestNettoyage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        livres, cls.rejets, cls.nb_lus = nettoyage.nettoyer(DOSSIER_TESTS / "donnees_exemple")
        cls.livres = {livre["titre"]: livre for livre in livres}

    def test_garde_seulement_les_bons_livres(self):
        self.assertEqual(self.nb_lus, 7)
        self.assertEqual(sorted(self.livres), ["L'étranger", "Le Hobbit"])
        self.assertEqual(self.rejets["pas en français"], 1)
        self.assertEqual(self.rejets["sans auteur"], 1)
        self.assertEqual(self.rejets["résumé absent ou trop court"], 1)

    def test_regroupe_les_editions(self):
        etranger = self.livres["L'étranger"]
        self.assertEqual(etranger["nb_editions"], 2)
        self.assertEqual(etranger["date_parution"], "1972")
        self.assertEqual(etranger["annee"], "1972")
        self.assertEqual(etranger["id_livre"], "ETR1972")
        self.assertEqual(etranger["isbn"], "9782070360000 | 9782070360024")
        self.assertEqual(etranger["mots_cles"], "Fantasy | Polar")
        self.assertEqual(etranger["categories"], "Fiction | Classique")

    def test_nettoie_resume_et_image(self):
        etranger = self.livres["L'étranger"]
        self.assertNotIn("<", etranger["description"])
        self.assertTrue(etranger["description"].endswith("Édition de poche."))
        self.assertTrue(etranger["couverture_google"].startswith("https://"))
        self.assertNotIn("edge=curl", etranger["couverture_google"])
        self.assertIn("& un trésor", self.livres["Le Hobbit"]["description"])

    def test_cle_auteur(self):
        self.assertEqual(nettoyage.cle_auteur("Camus, Albert"), nettoyage.cle_auteur("Albert Camus"))


if __name__ == "__main__":
    unittest.main()
