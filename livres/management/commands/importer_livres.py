"""Charge dans la base du site les fichiers créés par le dossier pipeline/.

    python manage.py importer_livres

Lit data/clean/livres.csv (étape 2), puis, s'ils existent, data/clean/couvertures.csv (étape 3)
et data/clean/similaires.csv (étape 4). On peut relancer la commande après chaque mise à jour
des données : les livres sont mis à jour, et les bibliothèques des utilisateurs sont conservées.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from livres.models import Livre, Similarite

SEPARATEUR_LISTE = " | "
CHAMPS_LIVRE = ["titre", "sous_titre", "auteurs", "editeur", "annee", "description",
                "categories", "nb_pages", "isbn", "couverture", "annee_couverture"]


def lire_csv(fichier):
    with fichier.open(encoding="utf-8-sig", newline="") as entree:
        return list(csv.DictReader(entree, delimiter=";"))


def nombre(texte):
    return int(texte) if str(texte).isdigit() else None


class Command(BaseCommand):
    help = "Importe les livres, couvertures et livres similaires préparés par le dossier pipeline/."

    def add_arguments(self, parser):
        parser.add_argument("--dossier", type=Path, default=settings.BASE_DIR / "data" / "clean",
                            help="dossier contenant livres.csv, couvertures.csv et similaires.csv")

    @transaction.atomic
    def handle(self, *args, **options):
        dossier = options["dossier"]
        fichier_livres = dossier / "livres.csv"
        if not fichier_livres.exists():
            raise CommandError(f"{fichier_livres} introuvable. Lance d'abord python pipeline/nettoyage.py")

        couvertures = {}
        if (dossier / "couvertures.csv").exists():
            couvertures = {ligne["id_livre"]: ligne for ligne in lire_csv(dossier / "couvertures.csv")}
        else:
            self.stdout.write("couvertures.csv absent : on garde les couvertures de Google Books.")

        livres = []
        for ligne in lire_csv(fichier_livres):
            couverture = couvertures.get(ligne["id_livre"], {})
            livres.append(Livre(
                id_livre=ligne["id_livre"],
                titre=ligne["titre"][:500],
                sous_titre=ligne["sous_titre"][:500],
                auteurs=ligne["auteurs"].replace(SEPARATEUR_LISTE, ", ")[:500],
                editeur=ligne["editeur"][:300],
                annee=nombre(ligne["annee"]),
                description=ligne["description"],
                categories=ligne["categories"].replace(SEPARATEUR_LISTE, ", ")[:500],
                nb_pages=nombre(ligne["nb_pages"]),
                isbn=ligne["isbn"].replace(SEPARATEUR_LISTE, ", ")[:500],
                couverture=couverture.get("url_couverture", ligne["couverture_google"]),
                annee_couverture=nombre(couverture.get("annee_edition", "")),
            ))
        Livre.objects.bulk_create(livres, batch_size=1000, update_conflicts=True,
                                  unique_fields=["id_livre"], update_fields=CHAMPS_LIVRE)
        self.stdout.write(f"{len(livres)} livres importés.")

        if (dossier / "similaires.csv").exists():
            connus = set(Livre.objects.values_list("id_livre", flat=True))
            Similarite.objects.all().delete()
            similarites = [
                Similarite(livre_id=l["id_livre"], similaire_id=l["id_similaire"],
                           rang=int(l["rang"]), score=float(l["score"]))
                for l in lire_csv(dossier / "similaires.csv")
                if l["id_livre"] in connus and l["id_similaire"] in connus
            ]
            Similarite.objects.bulk_create(similarites, batch_size=5000)
            self.stdout.write(f"{len(similarites)} liens de ressemblance importés.")
        else:
            self.stdout.write("similaires.csv absent : lance python pipeline/recommandations.py pour avoir des suggestions.")

        self.stdout.write(self.style.SUCCESS("Import terminé."))
