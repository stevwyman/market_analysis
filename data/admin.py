from django.contrib import admin
from .models import User, DataProvider, Security, Watchlist, Daily

# Register your models here.
admin.site.register(User)
admin.site.register(DataProvider)
admin.site.register(Security)
admin.site.register(Watchlist)
admin.site.register(Daily)
