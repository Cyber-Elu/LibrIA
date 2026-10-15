from django.contrib import admin

from .models import Livre, LivreBibliotheque, Similarite


@admin.register(Livre)
class LivreAdmin(admin.ModelAdmin):
    list_display = ["titre", "auteurs", "annee", "editeur"]
    search_fields = ["titre", "auteurs", "isbn"]


@admin.register(LivreBibliotheque)
class LivreBibliothequeAdmin(admin.ModelAdmin):
    list_display = ["utilisateur", "livre", "statut", "date_ajout"]
    list_filter = ["statut"]


@admin.register(Similarite)
class SimilariteAdmin(admin.ModelAdmin):
    list_display = ["livre", "similaire", "rang", "score"]
    raw_id_fields = ["livre", "similaire"]
