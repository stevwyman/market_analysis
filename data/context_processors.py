from .models import Watchlist

def watchlist_processor(request):
    
    return {"watchlists": Watchlist.objects.all()}
