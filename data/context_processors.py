from .models import User, Watchlist

def watchlist_processor(request):
    
    user = request.user
    watchlists = list()
    if user.is_authenticated:
        user = request.user

        for watchlist in Watchlist.objects.filter(visibility="AU").all():
            if watchlist not in watchlists:
                watchlists.append(watchlist)

        for watchlist in Watchlist.objects.filter(user=user).all():
            if watchlist not in watchlists:
                watchlists.append(watchlist)

        if user.role != User.BASIC:
            for watchlist in Watchlist.objects.filter(visibility="AP").all():
                if watchlist not in watchlists:
                    watchlists.append(watchlist)
        
    return {"watchlists": watchlists}
