from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("watchlists", views.watchlists, name="watchlists"),
    path("watchlist/<int:watchlist_id>/", views.watchlist, name="watchlist"),
    path("security/<int:security_id>/", views.security, name="security")
]