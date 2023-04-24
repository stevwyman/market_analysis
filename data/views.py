from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateformat import format

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib

matplotlib.use("agg")

from io import BytesIO
from datetime import datetime
import base64

from data.OnlineDAO import Online_DAO_Factory, Interval
from .models import Watchlist, Security, Daily, DataProvider
from .forms import WatchlistForm, SecurityForm

# Create your views here.


# main page get's rendered here
def index(request):
    return render(request, "data/index.html")


def watchlists(request):
    return render(
        request, "data/watchlists.html", {"watchlists": Watchlist.objects.all()}
    )


def watchlist_new(request):
    if request.method == "GET":
        form = WatchlistForm()
        return render(request, "data/watchlist_new.html", {"form": form})
    else:
        WatchlistForm(request.POST).save()
        return HttpResponseRedirect(reverse("watchlists"))


def watchlist_edit(request, watchlist_id):
    try:
        watchlist = Watchlist.objects.get(pk=watchlist_id)
    except ObjectDoesNotExist:
        messages.warning(request, "Watchlist not found")
        return HttpResponseRedirect(reverse("watchlists"))

    if request.method == "GET":
        form = WatchlistForm(instance=watchlist)
        return render(request, "data/watchlist_edit.html")
    else:
        WatchlistForm(request.POST).save()
        return HttpResponseRedirect(reverse("watchlists"))


def watchlist(request, watchlist_id):
    print(f"id: {watchlist_id}")

    watchlist = Watchlist.objects.get(pk=watchlist_id)
    securities = watchlist.securities.all()
    return render(
        request,
        "data/watchlist.html",
        {"watchlist": watchlist, "securities": securities},
    )


def security(request, security_id):
    print(f"security id: {security_id}")

    sec = Security.objects.get(pk=security_id)
    print(f"data provider {sec.data_provider} for {sec}")

    # User.objects.all().order_by('-id')[:10]
    daily = Daily.objects.filter(security=sec).all()[:200]
    daily_list = list(daily)
    daily_list.sort(key=lambda x: x.date, reverse=False)

    closes = list()
    dates = list()
    full_data = list()

    for entry in daily_list:
        dates.append(str(entry.date))
        closes.append(str(entry.close))
        candle = list()
        candle.append(int(format(entry.date, "U"))*1000)
        candle.append(float(entry.open_price))
        candle.append(float(entry.high_price))
        candle.append(float(entry.low))
        candle.append(float(entry.close))
        full_data.append(candle)

    return render(
        request,
        "data/security.html",
        {"security": sec, "labels": dates, "data": closes, "full_data": full_data},
    )


def security_new(request, watchlist_id):
    watchlist = Watchlist.objects.get(pk=watchlist_id)
    if request.method == "GET":
        form = SecurityForm()
        return render(
            request, "data/security_new.html", {"form": form, "watchlist": watchlist}
        )
    else:
        form = SecurityForm(request.POST)
        if form.is_valid():
            symbol = form.cleaned_data["symbol"]
            dataProvider = form.cleaned_data["data_provider"]
            print(f"looking up {symbol} with {dataProvider}")
            # check if this security is already in the database
            sec = Security.objects.filter(symbol=symbol, data_provider=dataProvider)
            print(f"found :{sec}")

            # looking up additional information
            online_dao = Online_DAO_Factory().get_online_dao(dataProvider)

            price = online_dao.lookupPrice(symbol)
            if price["error"] is None:
                # create new Security
                sec = Security(symbol=symbol, data_provider=dataProvider)
                shortName = price["shortName"]
                sec.name = shortName
                currencySymbol = price["currencySymbol"]
                sec.currency_symbol = currencySymbol
                currency = price["currency"]
                sec.currency = currency
                quoteType = price["quoteType"]
                # sec
                exchangeName = price["exchangeName"]
                sec.exchange = exchangeName
            else:
                messages.warning(request, price["error"])
                return HttpResponseRedirect(
                    reverse("watchlist", kwargs={"watchlist_id": watchlist.id})
                )

            summaryProfile = online_dao.lookupSymbol(symbol)
            if summaryProfile["error"] is None:
                country = summaryProfile["country"]
                sec.country = country
                industry = summaryProfile["industry"]
                sec.industry = industry
                sector = summaryProfile["sector"]
                sec.sector = sector
            else:
                messages.warning(request, summaryProfile["error"])

            sec.save()
            watchlist.securities.add(sec)
        else:
            print("form is not valid")
            print(form.errors.as_data())  # here you print errors to terminal
            messages.error(request, "Form is not valid")

        # SecurityForm(request.POST).save()
        return HttpResponseRedirect(
            reverse("watchlist", kwargs={"watchlist_id": watchlist.id})
        )


def history_update(request, security_id):
    sec = Security.objects.get(pk=security_id)
    online_dao = Online_DAO_Factory().get_online_dao(sec.data_provider)

    # request new history from online dao
    result = online_dao.lookupHistory(security=sec, look_back=2000)
    if len(result) > 10:
        # drop current history
        Daily.objects.filter(security=sec).delete()
        messages.info(request, "old history dropped")
        # crate new history
        Daily.objects.bulk_create(result)
        messages.info(request, "new history created")

    # forward to security overview page
    return HttpResponseRedirect(reverse("security", kwargs={"security_id": sec.id}))
