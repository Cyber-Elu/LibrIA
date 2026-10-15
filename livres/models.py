from django.conf import settings
from django.db import models
from django.urls import reverse


class Livre(models.Model):
    """Un livre, tel que préparé par les scripts du dossier pipeline/ (étapes 2 et 3)."""

    id_livre = models.CharField("identifiant", max_length=40, primary_key=True)
    titre = models.CharField(max_length=500)
    sous_titre = models.CharField(max_length=500, blank=True)
    auteurs = models.CharField(max_length=500)
    editeur = models.CharField(max_length=300, blank=True)
    annee = models.PositiveIntegerField("année de parution", null=True, blank=True)
    description = models.TextField("résumé")
    categories = models.CharField("catégories", max_length=500, blank=True)
    nb_pages = models.PositiveIntegerField("nombre de pages", null=True, blank=True)
    isbn = models.CharField("ISBN", max_length=500, blank=True)
    couverture = models.URLField(max_length=500, blank=True)
    annee_couverture = models.PositiveIntegerField("année de l'édition de la couverture", null=True, blank=True)

    class Meta:
        ordering = ["titre"]

    def __str__(self):
        return f"{self.titre} ({self.auteurs})"

    def get_absolute_url(self):
        return reverse("fiche_livre", args=[self.id_livre])


class Similarite(models.Model):
    """« similaire » ressemble à « livre » (étape 4). Rang 1 = le plus ressemblant."""

    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name="similarites")
    similaire = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name="+")
    rang = models.PositiveSmallIntegerField()
    score = models.FloatField()

    class Meta:
        ordering = ["livre", "rang"]
        constraints = [models.UniqueConstraint(fields=["livre", "similaire"], name="similarite_unique")]


class LivreBibliotheque(models.Model):
    """Un livre rangé dans la bibliothèque personnelle d'un utilisateur."""

    class Statut(models.TextChoices):
        LU = "lu", "Lu"
        EN_COURS = "en_cours", "En cours"
        A_LIRE = "a_lire", "À lire"

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bibliotheque")
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name="lecteurs")
    statut = models.CharField(max_length=10, choices=Statut.choices)
    date_ajout = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_ajout"]
        constraints = [models.UniqueConstraint(fields=["utilisateur", "livre"], name="un_statut_par_livre")]

    def __str__(self):
        return f"{self.utilisateur} : {self.livre.titre} ({self.get_statut_display()})"
