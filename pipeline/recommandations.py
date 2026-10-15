"""Étape 4 de LibrIA : trouver, pour chaque livre, les livres dont le contenu ressemble le plus.

1. Pour chaque livre de `data/clean/livres.csv`, on transforme le titre, les catégories et le résumé
   en une « empreinte » : une liste de nombres qui résume le sens du texte. C'est un petit modèle
   d'intelligence artificielle gratuit (sentence-transformers, multilingue) qui la calcule, sur ton PC.
2. Deux livres dont les empreintes sont proches parlent de choses proches. On mesure cette proximité
   avec la « similarité cosinus » : 1 = même sens, 0 = aucun rapport.
3. On garde les 20 livres les plus proches de chaque livre dans `data/clean/similaires.csv`.
   Le site web (étape 5) n'aura plus qu'à lire ce fichier : il répondra donc très vite.

Les empreintes sont enregistrées dans `data/clean/empreintes.npy` : si on relance le script,
seuls les nouveaux livres sont calculés.

Utilisation (depuis le dossier du projet) :
    python pipeline/recommandations.py
    python pipeline/recommandations.py --voisins 10
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nettoyage import FICHIER_SORTIE as FICHIER_LIVRES  # noqa: E402
from nettoyage import SEPARATEUR_LISTE  # noqa: E402

DOSSIER_CLEAN = Path(__file__).resolve().parent.parent / "data" / "clean"
FICHIER_EMPREINTES = DOSSIER_CLEAN / "empreintes.npy"
FICHIER_IDS = DOSSIER_CLEAN / "empreintes_ids.txt"
FICHIER_SORTIE = DOSSIER_CLEAN / "similaires.csv"

# Modèle gratuit qui comprend le français (≈ 500 Mo, téléchargé automatiquement la première fois).
NOM_MODELE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
NB_VOISINS = 20
TAILLE_BLOC = 1000  # on compare les livres par paquets pour ne pas saturer la mémoire du PC

COLONNES = ["id_livre", "id_similaire", "rang", "score"]


def texte_du_livre(livre):
    """Le texte qui représente le livre : titre, sous-titre, catégories puis résumé."""
    categories = livre["categories"].replace(SEPARATEUR_LISTE, ", ")
    morceaux = [livre["titre"], livre["sous_titre"], categories, livre["description"]]
    return ". ".join(m for m in morceaux if m)


def encodeur_sentence_transformers():
    """Charge le modèle (import ici, car la bibliothèque est longue à charger)."""
    from sentence_transformers import SentenceTransformer

    print(f"Chargement du modèle {NOM_MODELE} (long la première fois : téléchargement)...")
    modele = SentenceTransformer(NOM_MODELE)
    return lambda textes: modele.encode(textes, batch_size=64, show_progress_bar=True)


def normaliser_lignes(matrice):
    """Met chaque empreinte à la longueur 1 : la similarité cosinus devient un simple produit."""
    normes = np.linalg.norm(matrice, axis=1, keepdims=True)
    return matrice / np.where(normes == 0, 1, normes)


def calculer_empreintes(livres, encoder, empreintes_connues):
    """Réutilise les empreintes déjà calculées et ne calcule que celles des nouveaux livres."""
    a_calculer = [livre for livre in livres if livre["id_livre"] not in empreintes_connues]
    if a_calculer:
        print(f"{len(a_calculer)} empreintes à calculer ({len(livres) - len(a_calculer)} déjà connues).")
        nouvelles = np.asarray(encoder([texte_du_livre(livre) for livre in a_calculer]), dtype=np.float32)
        for livre, empreinte in zip(a_calculer, nouvelles):
            empreintes_connues[livre["id_livre"]] = empreinte
    matrice = np.stack([empreintes_connues[livre["id_livre"]] for livre in livres])
    return normaliser_lignes(matrice.astype(np.float32))


def plus_proches_voisins(empreintes, nb_voisins):
    """Pour chaque livre, renvoie [(indice du voisin, score), ...] du plus proche au moins proche."""
    nb_livres = len(empreintes)
    nb_voisins = min(nb_voisins, nb_livres - 1)
    resultats = []
    for debut in range(0, nb_livres, TAILLE_BLOC):
        bloc = empreintes[debut:debut + TAILLE_BLOC]
        scores = bloc @ empreintes.T  # similarité cosinus de ce paquet avec tous les livres
        for i in range(len(bloc)):
            scores[i, debut + i] = -np.inf  # un livre n'est pas son propre voisin
        if nb_voisins <= 0:
            resultats.extend([] for _ in bloc)
            continue
        meilleurs = np.argpartition(-scores, nb_voisins - 1, axis=1)[:, :nb_voisins]
        for i, indices in enumerate(meilleurs):
            indices = indices[np.argsort(-scores[i, indices])]
            resultats.append([(int(j), float(scores[i, j])) for j in indices])
    return resultats


def lire_empreintes():
    if not (FICHIER_EMPREINTES.exists() and FICHIER_IDS.exists()):
        return {}
    ids = FICHIER_IDS.read_text(encoding="utf-8").split()
    return dict(zip(ids, np.load(FICHIER_EMPREINTES)))


def enregistrer_empreintes(livres, empreintes):
    DOSSIER_CLEAN.mkdir(parents=True, exist_ok=True)
    np.save(FICHIER_EMPREINTES, empreintes)
    FICHIER_IDS.write_text("\n".join(livre["id_livre"] for livre in livres), encoding="utf-8")


def recommander(livres, encoder, nb_voisins=NB_VOISINS, empreintes_connues=None):
    """Renvoie (empreintes, lignes du CSV des livres similaires)."""
    empreintes = calculer_empreintes(livres, encoder, dict(empreintes_connues or {}))
    lignes = []
    for livre, voisins in zip(livres, plus_proches_voisins(empreintes, nb_voisins)):
        for rang, (j, score) in enumerate(voisins, start=1):
            lignes.append({
                "id_livre": livre["id_livre"], "id_similaire": livres[j]["id_livre"],
                "rang": rang, "score": round(score, 4),
            })
    return empreintes, lignes


def main():
    parser = argparse.ArgumentParser(description="Calcul des livres similaires.")
    parser.add_argument("--livres", type=Path, default=FICHIER_LIVRES, help="CSV créé par l'étape 2")
    parser.add_argument("--voisins", type=int, default=NB_VOISINS, help="nombre de livres similaires à garder")
    args = parser.parse_args()

    if not args.livres.exists():
        sys.exit(f"Fichier {args.livres} introuvable. Lance d'abord l'étape 2 (nettoyage.py).")
    with args.livres.open(encoding="utf-8-sig", newline="") as entree:
        livres = list(csv.DictReader(entree, delimiter=";"))
    if len(livres) < 2:
        sys.exit("Il faut au moins 2 livres pour chercher des ressemblances.")

    connues = lire_empreintes()
    encoder = encodeur_sentence_transformers() if any(l["id_livre"] not in connues for l in livres) else None
    empreintes, lignes = recommander(livres, encoder, args.voisins, connues)
    enregistrer_empreintes(livres, empreintes)

    with FICHIER_SORTIE.open("w", encoding="utf-8-sig", newline="") as sortie:
        ecrivain = csv.DictWriter(sortie, fieldnames=COLONNES, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"{len(lignes)} suggestions enregistrées pour {len(livres)} livres dans {FICHIER_SORTIE}")

    # Petit aperçu pour vérifier à l'œil que les suggestions ont du sens.
    titres = {livre["id_livre"]: livre["titre"] for livre in livres}
    print(f"\nExemple : livres proches de « {livres[0]['titre']} »")
    for ligne in [l for l in lignes if l["id_livre"] == livres[0]["id_livre"]][:5]:
        print(f"  {ligne['score']:.2f}  {titres[ligne['id_similaire']]}")


if __name__ == "__main__":
    main()
