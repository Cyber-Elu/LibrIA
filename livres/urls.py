from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("recherche/", views.recherche, name="recherche"),
    path("livre/<str:id_livre>/", views.fiche_livre, name="fiche_livre"),
    path("livre/<str:id_livre>/ranger/", views.changer_statut, name="changer_statut"),
    path("ma-bibliotheque/", views.bibliotheque, name="bibliotheque"),
    path("pour-toi/", views.pour_toi, name="pour_toi"),
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", auth_views.LoginView.as_view(template_name="registration/connexion.html"), name="connexion"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
]
