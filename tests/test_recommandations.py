"""Vérifie le calcul des livres similaires avec un faux modèle (aucun téléchargement).

Lancer depuis le dossier du projet :
    python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))

import recommandations  # noqa: E402

VOCABULAIRE = ["dragon", "magie", "enquete", "meurtre", "cuisine"]


def faux_encodeur(textes):
    """Compte quelques mots-clés : assez pour savoir quels textes se ressemblent."""
    return np.array([[texte.lower().count(mot) for mot in VOCABULAIRE] for texte in textes], dtype=float)


def livre(identifiant, description):
    return {"id_livre": identifiant, "titre": identifiant, "sous_titre": "", "categories": "", "description": description}


LIVRES = [
    livre("A", "Un dragon et de la magie."),
    livre("B", "La magie d'un dragon, encore un dragon."),
    livre("C", "Une enquete sur un meurtre."),
    livre("D", "Un meurtre, une enquete, un autre meurtre."),
    livre("E", "De la cuisine et un peu de magie."),
]


class TestRecommandations(unittest.TestCase):
    def test_voisins_les_plus_proches(self):
        _, lignes = recommandations.recommander(LIVRES, faux_encodeur, nb_voisins=2)
        premiers = {l["id_livre"]: l["id_similaire"] for l in lignes if l["rang"] == 1}
        self.assertEqual(premiers, {"A": "B", "B": "A", "C": "D", "D": "C", "E": "A"})
        self.assertEqual(len(lignes), 10)
        self.assertTrue(all(l["id_livre"] != l["id_similaire"] for l in lignes))

    def test_scores_tries(self):
        _, lignes = recommandations.recommander(LIVRES, faux_encodeur, nb_voisins=4)
        scores_a = [l["score"] for l in lignes if l["id_livre"] == "A"]
        self.assertEqual(scores_a, sorted(scores_a, reverse=True))
        self.assertLessEqual(max(scores_a), 1.0)

    def test_ne_recalcule_pas_les_empreintes_connues(self):
        empreintes, _ = recommandations.recommander(LIVRES, faux_encodeur, nb_voisins=2)
        connues = {l["id_livre"]: e for l, e in zip(LIVRES, empreintes)}
        nouveau = livre("F", "Un dragon cuisine.")
        vus = []

        def encodeur_espion(textes):
            vus.extend(textes)
            return faux_encodeur(textes)

        recommandations.recommander(LIVRES + [nouveau], encodeur_espion, 2, connues)
        self.assertEqual(vus, ["F. Un dragon cuisine."])

    def test_blocs(self):
        """Le découpage en paquets donne le même résultat qu'un seul calcul."""
        empreintes = recommandations.normaliser_lignes(np.random.default_rng(0).random((25, 8)))
        taille = recommandations.TAILLE_BLOC
        try:
            recommandations.TAILLE_BLOC = 7
            par_blocs = recommandations.plus_proches_voisins(empreintes, 3)
        finally:
            recommandations.TAILLE_BLOC = taille
        self.assertEqual(par_blocs, recommandations.plus_proches_voisins(empreintes, 3))


if __name__ == "__main__":
    unittest.main()
