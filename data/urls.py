from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("watchlists", views.watchlists, name="watchlists"),
    path("watchlist_new", views.watchlist_new, name="watchlist_new"),
    path("watchlist_edit/<int:watchlist_id>", views.watchlist_edit, name="watchlist_edit"),
    path("watchlist/<int:watchlist_id>/", views.watchlist, name="watchlist"),
    path("security/<int:security_id>/", views.security, name="security"),
    path("security_new/<int:watchlist_id>", views.security_new, name="security_new"),
    path("history_update/<int:security_id>", views.history_update, name="history_update"),
    path("tp/<int:security_id>", views.technical_parameter, name="technical_parameter"),
]