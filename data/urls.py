from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("start", views.start, name="start"),
    path("limit_new", views.limit_new, name="limit_new"),
    path("limit_edit/<int:limit_id>", views.limit_edit, name="limit_edit"),
    path("limit_drop/<int:limit_id>", views.limit_drop, name="limit_drop"),
    path("watchlists", views.watchlists, name="watchlists"),
    
    path("watchlist_new", views.watchlist_new, name="watchlist_new"),
    path("watchlist_edit/<int:watchlist_id>", views.watchlist_edit, name="watchlist_edit"),
    path("watchlist_drop/<int:watchlist_id>", views.watchlist_drop, name="watchlist_drop"),
    path("watchlist/<int:watchlist_id>/", views.watchlist, name="watchlist"),
    
    path("security/<int:security_id>/", views.security, name="security"),
    path("security_new/<int:watchlist_id>", views.security_new, name="security_new"),
    path("security_drop/<int:security_id>", views.security_drop, name="security_drop"),
    path("security_history/<int:security_id>", views.security_history, name="security_history"),
    path("security_search", views.security_search, name="security_search"),
    
    path("history_update/<int:security_id>", views.history_update, name="history_update"),
    path("tp/<int:security_id>", views.technical_parameter, name="technical_parameter"),
    path("ta/<int:security_id>", views.tech_analysis, name="tech_analysis"),
    path("fa/<int:security_id>", views.fundamental_analysis, name="fundamental_analysis"),
    
    path("update_by_provider/<str:data_provider>", views.update_by_provider, name="update_by_provider"),
    path("open_interest/<str:underlying>", views.open_interest, name="open_interest"),
    path("max_pain_history/<str:underlying>", views.max_pain_history, name="max_pain_history"),
    path("max_pain_distribution/<str:underlying>", views.max_pain_distribution, name="max_pain_distribution"),

    path("corp_bonds", views.corp_bonds, name="corp_bonds"),
    path("corp_bonds_data/<str:type>", views.corp_bonds_data, name="corp_bonds_data"),

    # sentiment
    path("sentiment", views.sentiment, name="sentiment"),

    # market diary
    path("md", views.market_diary, name="market_diary"),

    # build_data_set
    path("bds", views.build_data_set, name="build_data_set"),

    # admin 
    # create_default_lists
    path("cdl", views.create_default_lists, name="create_default_list"),
    # create a S&P 500 list and fill it with data
    path("cspl", views.create_sp500_list, name="create_sp500_list"),

    # managing participants
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register")
]