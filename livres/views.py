from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Livre, LivreBibliotheque, Similarite

LIVRES_PAR_PAGE = 24


def accueil(request):
    decouverte = Livre.objects.exclude(couverture="").order_by("?")[:12]
    return render(request, "livres/accueil.html", {"livres": decouverte})


def recherche(request):
    texte = request.GET.get("q", "").strip()
    livres = Livre.objects.none()
    if texte:
        livres = Livre.objects.all()
        for mot in texte.split():  # chaque mot doit apparaître dans le titre ou l'auteur
            livres = livres.filter(Q(titre__icontains=mot) | Q(auteurs__icontains=mot))
    page = Paginator(livres, LIVRES_PAR_PAGE).get_page(request.GET.get("page"))
    return render(request, "livres/recherche.html", {"q": texte, "page": page})


def fiche_livre(request, id_livre):
    livre = get_object_or_404(Livre, pk=id_livre)
    similaires = [s.similaire for s in livre.similarites.select_related("similaire")[:12]]
    statut = None
    if request.user.is_authenticated:
        rangement = LivreBibliotheque.objects.filter(utilisateur=request.user, livre=livre).first()
        statut = rangement.statut if rangement else None
    return render(request, "livres/fiche.html", {
        "livre": livre, "similaires": similaires, "statut": statut,
        "statuts": LivreBibliotheque.Statut.choices,
    })


@login_required
@require_POST
def changer_statut(request, id_livre):
    """Range le livre dans « Lu », « En cours » ou « À lire », ou le retire de la bibliothèque."""
    livre = get_object_or_404(Livre, pk=id_livre)
    statut = request.POST.get("statut")
    if statut in LivreBibliotheque.Statut.values:
        LivreBibliotheque.objects.update_or_create(
            utilisateur=request.user, livre=livre, defaults={"statut": statut})
        messages.success(request, f"« {livre.titre} » rangé dans : {LivreBibliotheque.Statut(statut).label}.")
    elif statut == "retirer":
        LivreBibliotheque.objects.filter(utilisateur=request.user, livre=livre).delete()
        messages.success(request, f"« {livre.titre} » retiré de ta bibliothèque.")
    suivant = request.POST.get("suivant", "")
    if not url_has_allowed_host_and_scheme(suivant, allowed_hosts={request.get_host()}):
        suivant = livre.get_absolute_url()
    return redirect(suivant)


@login_required
def bibliotheque(request):
    rangements = request.user.bibliotheque.select_related("livre")
    etageres = [
        (label, [r.livre for r in rangements if r.statut == valeur])
        for valeur, label in LivreBibliotheque.Statut.choices
    ]
    return render(request, "livres/bibliotheque.html", {"etageres": etageres})


def suggestions_pour(utilisateur, nombre=24):
    """Les livres qui ressemblent le plus à ceux que l'utilisateur a lus ou est en train de lire.

    Chaque livre lu « vote » pour ses livres similaires avec leur score de ressemblance ;
    on additionne les votes et on enlève les livres déjà présents dans la bibliothèque.
    """
    rangements = LivreBibliotheque.objects.filter(utilisateur=utilisateur)
    deja_ranges = rangements.values("livre")
    lus = rangements.filter(statut__in=[LivreBibliotheque.Statut.LU, LivreBibliotheque.Statut.EN_COURS]).values("livre")
    votes = (
        Similarite.objects.filter(livre__in=lus)
        .exclude(similaire__in=deja_ranges)
        .values("similaire")
        .annotate(total=Sum("score"))
        .order_by("-total")[:nombre]
    )
    ordre = [v["similaire"] for v in votes]
    livres = Livre.objects.in_bulk(ordre)
    return [livres[i] for i in ordre]


@login_required
def pour_toi(request):
    a_des_lectures = request.user.bibliotheque.filter(
        statut__in=[LivreBibliotheque.Statut.LU, LivreBibliotheque.Statut.EN_COURS]).exists()
    return render(request, "livres/pour_toi.html", {
        "livres": suggestions_pour(request.user), "a_des_lectures": a_des_lectures,
    })


def inscription(request):
    if request.user.is_authenticated:
        return redirect("accueil")
    formulaire = UserCreationForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        utilisateur = formulaire.save()
        login(request, utilisateur)
        messages.success(request, f"Bienvenue {utilisateur.username} ! Ton compte est créé.")
        return redirect("accueil")
    return render(request, "registration/inscription.html", {"form": formulaire})
