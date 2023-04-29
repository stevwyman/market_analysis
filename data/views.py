from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger, Page
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateformat import format

from datetime import datetime, date
from data.technical_analysis import EMA, SMA, Hurst

import json

from data.OnlineDAO import Online_DAO_Factory, Interval
from .models import Watchlist, Security, Daily, DailyUpdate, DataProvider
from .forms import WatchlistForm, SecurityForm
from .helper import humanize_price

# Create your views here.

RGB_RED = "rgba(255,82,82, 0.8)"
RGB_GREEN = "rgba(0, 150, 136, 0.8)"


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
        form = WatchlistForm(request.POST)
        if form.is_valid:
            form.save()
            messages.info(request, "Created new watchlist")
        else:
            print(form.errors.as_data())
            messages.error(request, "Could not create new watchlist")

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


def watchlist(request, watchlist_id:int):

    watchlist = Watchlist.objects.get(pk=watchlist_id)
    securities = watchlist.securities.order_by("name").all()

    # building watchlist
    watchlist_entries = list()
    for security in securities:
        watchlist_entry = {}
        watchlist_entry["security"] = security
        price_dao = Online_DAO_Factory().get_online_dao(security.data_provider)
        watchlist_entry["price"] = humanize_price(price_dao.lookupPrice(security.symbol))
        try:
            history = security.daily_data.all()[:55]
            watchlist_entry["sma"] = SMA(50).latest(history)
        except ValueError as va:
            messages.warning(request, va)

        watchlist_entries.append(watchlist_entry)


    # sorting
    order_by = request.GET.get("order_by", "name")
    direction = request.GET.get("direction", "asc")
    if direction == "desc":
        _b_direction = True
    else:
        _b_direction = False
    print(f"sorting {direction} by {order_by}")
    if order_by == "change":
        watchlist_entries.sort(key=lambda x: x["price"]["change_percent"], reverse=_b_direction)
    elif order_by == "hurst":
        watchlist_entries.sort(key=lambda x: x["sma"]["hurst"], reverse=_b_direction)
    elif order_by == "spread":
        watchlist_entries.sort(key=lambda x: x["sma"]["sd"], reverse=_b_direction)

    # pagination
    paginator = Paginator(watchlist_entries, 10)
    page_num = request.GET.get("page", 1)

    try:
        paged_watchlist_entries = paginator.page(page_num)
    except PageNotAnInteger:
        # if page is not an integer, deliver the first page
        paged_watchlist_entries = paginator.page(1)
    except EmptyPage:
        # if the page is out of range, deliver the last page
        paged_watchlist_entries = paginator.page(paginator.num_pages)

    return render(
        request,
        "data/watchlist.html",
        {"watchlist": watchlist, "watchlist_entries":paged_watchlist_entries, "order_by": order_by, "direction": direction}
    )


def security(request, security_id):
    print(f"security id: {security_id}")

    sec = Security.objects.get(pk=security_id)
    print(f"data provider {sec.data_provider} for {sec}")

    daily = sec.daily_data.all()[:1000]

    prices_data = list()
    ema50_data = list()
    ema50 = EMA(50)

    ema20_data = list()
    ema20 = EMA(20)
    volume_data = list()

    hurst = Hurst()
    hurst_data = list()

    sma50 = SMA(50)
    sma50_sd = 0

    previous_close = 0
    for entry in reversed(daily):
        # building the prices data using time and ohlc
        candle = {}
        candle["time"] = str(entry.date)
        candle["open"] = float(entry.open_price)
        candle["high"] = float(entry.high_price)
        candle["low"] = float(entry.low)
        candle["close"] = float(entry.close)
        prices_data.append(candle)
        hurst_data.append(float(entry.close))

        sma50.add(float(entry.close))
        sma50_sd = sma50.sigma_delta

        ema50_value = ema50.add(float(entry.close))
        if ema50_value is not None:
            ema50_entry = {}
            ema50_entry["time"] = str(entry.date)
            ema50_entry["value"] = ema50_value
            ema50_data.append(ema50_entry)

        ema20_value = ema20.add(float(entry.close))
        if ema20_value is not None:
            ema20_entry = {}
            ema20_entry["time"] = str(entry.date)
            ema20_entry["value"] = ema20_value
            ema20_data.append(ema20_entry)
        

        volume = {}
        volume["time"] = str(entry.date)
        volume["value"] = float(entry.volume)
        if candle["close"] >= previous_close:
            volume["color"] = RGB_GREEN
        else:
            volume["color"] = RGB_RED
        volume_data.append(volume)

        previous_close = candle["close"]

    hurst_value = hurst.hurst(input_ts=hurst_data)
    print(f"current hurst value: {hurst_value}")

    # looking up additional information
    online_dao = Online_DAO_Factory().get_online_dao(sec.data_provider)
    price = online_dao.lookupPrice(sec.symbol)

    if price["quoteType"] == "EQUITY":
        defaultKeyStatistics = online_dao.lookupDefaultKeyStatistics(sec.symbol)
    else:
        defaultKeyStatistics = {}


    return render(
        request,
        "data/security.html",
        {
            "security": sec,
            "full_data": prices_data,
            "ema50": ema50_data,
            "ema20": ema20_data,
            "sma50_sd": sma50_sd,
            "volume": volume_data,
            "hurst_value": hurst_value,
            "price":humanize_price(price),
            "price_orig":price,
            "defaultKeyStatistics":defaultKeyStatistics
        },
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
            
            # looking up additional information
            online_dao = Online_DAO_Factory().get_online_dao(dataProvider)

            price = online_dao.lookupPrice(symbol)
            # print(price)
            try:
                messages.warning(request, price["error"])
                return HttpResponseRedirect(
                    reverse("watchlist", kwargs={"watchlist_id": watchlist.id})
                )
            except:
                pass

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

            summaryProfile = online_dao.lookupSymbol(symbol)
            try:
                country = summaryProfile["country"]
                sec.country = country
                industry = summaryProfile["industry"]
                sec.industry = industry
                sector = summaryProfile["sector"]
                sec.sector = sector
            except:
                messages.warning(request, summaryProfile["error"])

            sec.save()
            watchlist.securities.add(sec)

            #
            # add initial history for this entry
            #
            online_dao = Online_DAO_Factory().get_online_dao(sec.data_provider)

            # request new history from online dao
            result = online_dao.lookupHistory(security=sec, look_back=2000)
            if len(result) > 10:

                try:
                    with transaction.atomic():
                        # drop current history
                        Daily.objects.filter(security=sec).delete()
                        try:
                            DailyUpdate.objects.get(security=sec).delete()
                        except:
                            pass

                        # crate new history
                        Daily.objects.bulk_create(result)
                        DailyUpdate.objects.create(security=sec)
                        messages.info(request, "History has been updated")

                except DatabaseError as db_error:
                    print(db_error)
                    messages.warning(request, "Error while updating")

        else:
            if "__all__" in form.errors:
                error_data = form.errors["__all__"]
                for e in error_data:
                    if e == "Security with this Symbol and Data provider already exists.":
                        sec = Security.objects.get(symbol=form.data["symbol"], data_provider=form.data["data_provider"])
                        watchlist.securities.add(sec)
                        messages.info(request, "Added " + str(sec) + " to watchlist")
                        return HttpResponseRedirect(
                            reverse("watchlist", kwargs={"watchlist_id": watchlist.id})
                        )

            print("form is not valid")
            print(form.errors.as_data())  # here you print errors to terminal
            messages.error(request, "Form is not valid")

        return HttpResponseRedirect(
            reverse("watchlist", kwargs={"watchlist_id": watchlist.id})
        )


def security_drop(request, watchlist_id):
    """
    remove the security from the given watchlist and if no other holds a reference, drop the security and the elated data
    """    
    watchlist = Watchlist.objects.get(pk=watchlist_id)
    if request.method == "POST":

        print(request.body)
        request.POST.get("security_id", "")
        # provided_data = json.loads(request.body)
        
        security_id = request.POST.get("security_id", "")
        security = Security.objects.get(pk=security_id)
        watchlist.securities.remove(security)

        related_watchlists = security.watchlists.all()
        if related_watchlists.count() == 0:
            security.delete()
            print(f"removed {security_id}")
    return HttpResponseRedirect(
            reverse("watchlist", kwargs={"watchlist_id": watchlist.id})
        )  
        

def history_update(request, security_id):

    sec = Security.objects.get(pk=security_id)
    _today = date.today()

    last_updated = sec.dailyupdate_data.all().first()
    if last_updated is not None:
        print(f"last update: {last_updated.date}")
        if last_updated.date == _today:
            print("no update required, already updated today")
            messages.info(request, "Already up to date.")
            # forward to security overview page
            return HttpResponseRedirect(reverse("security", kwargs={"security_id": sec.id}))

    online_dao = Online_DAO_Factory().get_online_dao(sec.data_provider)

    # request new history from online dao
    result = online_dao.lookupHistory(security=sec, look_back=2000)
    if len(result) > 10:

        try:
            with transaction.atomic():
                # drop current history
                Daily.objects.filter(security=sec).delete()
                try:
                    DailyUpdate.objects.get(security=sec).delete()
                except:
                    pass

                # crate new history
                Daily.objects.bulk_create(result)
                DailyUpdate.objects.create(security=sec)
                messages.info(request, "History has been updated")

        except DatabaseError as db_error:
            print(db_error)
            messages.warning(request, "Error while updating")

    # forward to security overview page
    return HttpResponseRedirect(reverse("security", kwargs={"security_id": sec.id}))


def technical_parameter(request, security_id):
    sec = Security.objects.get(pk=security_id)

    if request.method == "POST":

        print(request.body)
         
        provided_data = json.loads(request.body)
        print(f"technical parameter for {sec} requested")
        
        data = {}
        if provided_data["view"] == "sd":
            
            daily = sec.daily_data.all()[:200]

            hurst_data = list()
            sma50 = SMA(50)

            for entry in reversed(daily):

                sma50.add(float(entry.close))
                sd_value = sma50.sigma_delta()
                if sd_value is not None:
                    sd_entry = {}
                    sd_entry['time'] = str(entry.date)
                    sd_entry['value'] = sd_value
                    hurst_data.append(sd_entry)

            data["tp_data"] = json.dumps(hurst_data)
        elif provided_data["view"] == "hurst":
            daily = sec.daily_data.all()[:400]

            hurst_data = list()
            sma50 = SMA(50)

            for entry in reversed(daily):

                sma50.add(float(entry.close))
                sd_value = sma50.sigma_delta()
                if sd_value is not None:
                    sd_entry = {}
                    sd_entry['time'] = str(entry.date)
                    sd_entry['value'] = sma50.hurst()
                    hurst_data.append(sd_entry)

            data["tp_data"] = json.dumps(hurst_data)
        
        return JsonResponse(data, status=201)

