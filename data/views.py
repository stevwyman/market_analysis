from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib
matplotlib.use('agg')

from io import BytesIO
from datetime import datetime
import base64

from data.OnlineDAO import YahooOnlineDAO, Interval
from .models import Watchlist, Security, Daily, DataProvider
from .forms import WatchlistForm

# Create your views here.

# main page get's rendered here
def index(request):
    return render(request, "data/index.html")


def watchlists(request):
    

    return render(request, "data/watchlists.html", {"watchlists": Watchlist.objects.all()})

def new_watchlist(request):

    if request.method == "GET":
        form = WatchlistForm()
        return render(request, "data/watchlist.html")
    else:
        WatchlistForm(request.POST).save()
        return HttpResponseRedirect(reverse("watchlists"))

def watchlist(request, watchlist_id):

    print(f"id: {watchlist_id}")

    watchlist = Watchlist.objects.get(pk=watchlist_id)
    securities = watchlist.securities.all()
    return render(request, "data/watchlist.html", {"securities": securities})

def security(request, security_id):

    print(f"security id: {security_id}")

    sec = Security.objects.get(pk=security_id)
    print(f"data provider {sec.data_provider} for {sec}")

    daily = Daily.objects.filter(security=sec).all()

    closes = list()
    dates = list()
    for entry in daily:
        dates.append(datetime.strptime(str(entry.date), "%Y-%m-%d"))
        closes.append(entry.close)


    plt.title("Corp. High Yield Bonds A-D Line")
    plt.ylabel("Value")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
    plt.plot(dates, closes, label="a-d line")
    plt.gcf().autofmt_xdate()
    plt.legend()

    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()

    graphic = base64.b64encode(image_png)
    graphic = graphic.decode('utf-8')

    return render(request, "data/security.html",{"graphic":graphic})
    
