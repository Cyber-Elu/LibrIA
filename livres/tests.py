import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Livre, LivreBibliotheque, Similarite
from .views import suggestions_pour


def creer_livre(identifiant, titre, auteurs="Auteur"):
    return Livre.objects.create(id_livre=identifiant, titre=titre, auteurs=auteurs, description="Un résumé.")


class TestImport(TestCase):
    def test_importe_les_trois_fichiers(self):
        dossier = Path(tempfile.mkdtemp())
        entete = ("id_livre;titre;sous_titre;auteurs;editeur;date_parution;annee;description;categories;"
                  "mots_cles;nb_pages;isbn;ids_google;couverture_google;nb_editions\n")
        (dossier / "livres.csv").write_text(
            entete
            + "A;L'étranger;;Camus, Albert;Gallimard;1972;1972;Meursault...;Fiction;Polar;180;978A | 978B;A;https://g/a.jpg;2\n"
            + "B;La peste;;Albert Camus;;;;Oran...;;;;;B;https://g/b.jpg;1\n",
            encoding="utf-8-sig")
        (dossier / "couvertures.csv").write_text(
            "id_livre;source;url_couverture;annee_edition;oeuvre_openlibrary;edition_openlibrary\n"
            "A;openlibrary;https://covers.openlibrary.org/b/id/1-L.jpg;1957;/works/OL1W;/books/OL2M\n",
            encoding="utf-8-sig")
        (dossier / "similaires.csv").write_text(
            "id_livre;id_similaire;rang;score\nA;B;1;0.8\nB;A;1;0.8\nB;INCONNU;2;0.5\n", encoding="utf-8-sig")

        call_command("importer_livres", dossier=dossier, stdout=open(dossier / "log.txt", "w"))
        call_command("importer_livres", dossier=dossier, stdout=open(dossier / "log.txt", "w"))  # relançable

        etranger = Livre.objects.get(pk="A")
        self.assertEqual(etranger.couverture, "https://covers.openlibrary.org/b/id/1-L.jpg")
        self.assertEqual(etranger.annee_couverture, 1957)
        self.assertEqual(etranger.isbn, "978A, 978B")
        self.assertEqual(Livre.objects.get(pk="B").couverture, "https://g/b.jpg")
        self.assertIsNone(Livre.objects.get(pk="B").annee)
        self.assertEqual(Similarite.objects.count(), 2)


class TestSite(TestCase):
    def setUp(self):
        self.etranger = creer_livre("A", "L'étranger", "Albert Camus")
        self.peste = creer_livre("B", "La peste", "Albert Camus")
        self.hobbit = creer_livre("C", "Le Hobbit", "J.R.R. Tolkien")
        self.chute = creer_livre("D", "La chute", "Albert Camus")
        Similarite.objects.create(livre=self.etranger, similaire=self.peste, rang=1, score=0.9)
        Similarite.objects.create(livre=self.etranger, similaire=self.chute, rang=2, score=0.6)
        Similarite.objects.create(livre=self.hobbit, similaire=self.chute, rang=1, score=0.2)
        self.lectrice = User.objects.create_user("lectrice", password="un-mot-de-passe-solide")

    def test_pages_publiques(self):
        for url in [reverse("accueil"), reverse("recherche") + "?q=camus peste", self.etranger.get_absolute_url()]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        resultats = self.client.get(reverse("recherche"), {"q": "camus peste"}).context["page"].object_list
        self.assertEqual(list(resultats), [self.peste])

    def test_fiche_montre_les_livres_similaires(self):
        reponse = self.client.get(self.etranger.get_absolute_url())
        self.assertEqual(reponse.context["similaires"], [self.peste, self.chute])

    def test_inscription_connecte_l_utilisateur(self):
        reponse = self.client.post(reverse("inscription"), {
            "username": "nouveau", "password1": "Lecture-2026!", "password2": "Lecture-2026!"})
        self.assertRedirects(reponse, reverse("accueil"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get(username="nouveau").pk)

    def test_bibliotheque_reservee_aux_comptes(self):
        reponse = self.client.get(reverse("bibliotheque"))
        self.assertRedirects(reponse, reverse("connexion") + "?next=" + reverse("bibliotheque"))
        reponse = self.client.post(reverse("changer_statut", args=["A"]), {"statut": "lu"})
        self.assertEqual(LivreBibliotheque.objects.count(), 0)

    def test_ranger_changer_et_retirer(self):
        self.client.force_login(self.lectrice)
        url = reverse("changer_statut", args=["A"])
        self.client.post(url, {"statut": "a_lire"})
        self.client.post(url, {"statut": "lu"})
        rangement = LivreBibliotheque.objects.get(utilisateur=self.lectrice)
        self.assertEqual(rangement.statut, "lu")
        etageres = dict(self.client.get(reverse("bibliotheque")).context["etageres"])
        self.assertEqual(etageres["Lu"], [self.etranger])
        self.client.post(url, {"statut": "retirer"})
        self.assertFalse(LivreBibliotheque.objects.exists())

    def test_redirection_externe_refusee(self):
        self.client.force_login(self.lectrice)
        reponse = self.client.post(reverse("changer_statut", args=["A"]),
                                   {"statut": "lu", "suivant": "https://site-pirate.example/"})
        self.assertRedirects(reponse, self.etranger.get_absolute_url())

    def test_suggestions_pour_toi(self):
        LivreBibliotheque.objects.create(utilisateur=self.lectrice, livre=self.etranger, statut="lu")
        LivreBibliotheque.objects.create(utilisateur=self.lectrice, livre=self.hobbit, statut="en_cours")
        LivreBibliotheque.objects.create(utilisateur=self.lectrice, livre=self.peste, statut="a_lire")
        # La peste est déjà « À lire » : on ne la propose pas. La chute cumule 0.6 + 0.2.
        self.assertEqual(suggestions_pour(self.lectrice), [self.chute])
        self.client.force_login(self.lectrice)
        self.assertEqual(self.client.get(reverse("pour_toi")).status_code, 200)

    def test_chaque_utilisateur_a_sa_bibliotheque(self):
        autre = User.objects.create_user("autre", password="un-autre-mot-de-passe")
        LivreBibliotheque.objects.create(utilisateur=autre, livre=self.etranger, statut="lu")
        self.client.force_login(self.lectrice)
        etageres = dict(self.client.get(reverse("bibliotheque")).context["etageres"])
        self.assertEqual(etageres["Lu"], [])
