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
from data.technical_analysis import EMA, SMA, Hurst, BollingerBands

import json

from data.OnlineDAO import Online_DAO_Factory, Interval
from .models import Watchlist, Security, Daily, DailyUpdate, Weekly, WeeklyUpdate, Monthly, MonthlyUpdate
from .forms import WatchlistForm, SecurityForm
from .helper import humanize_price, humanize_fundamentals

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
        dao = Online_DAO_Factory().get_online_dao(security.data_provider)
        watchlist_entry["price"] = humanize_price(dao.lookupPrice(security.symbol))
        watchlist_entry["fundamentals"] = humanize_fundamentals(dao.lookup_financial_data(security), dao.lookup_default_key_statistics(security), dao.lookup_summary_detail(security))
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
    elif order_by == "pef":
        watchlist_entries.sort(key=lambda x: x["fundamentals"]["pe_forward"], reverse=_b_direction)

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

    fundamentals = {}
    if price["quoteType"] == "EQUITY":
        quoteSummary = online_dao.lookup_summary_detail(sec)
        fundamentals = humanize_fundamentals(online_dao.lookup_financial_data(sec), online_dao.lookup_default_key_statistics(sec), online_dao.lookup_summary_detail(sec))
    else:
        quoteSummary = {}


    return render(
        request,
        "data/security.html",
        {
            "security": sec,
            "hurst_value": hurst_value,
            "price":humanize_price(price),
            "fundamentals": fundamentals,
            "quote_summary":quoteSummary
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
            sec.name = price["shortName"]
            sec.currency_symbol = price["currencySymbol"]
            sec.currency = price["currency"]
            sec.type = price["quoteType"]
            sec.exchange = price["exchangeName"]

            summaryProfile = online_dao.lookupSymbol(symbol)
            try:
                sec.country = summaryProfile["country"]
                sec.industry = summaryProfile["industry"]
                sec.sector = summaryProfile["sector"]
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
    interval = request.GET.get("interval", "d")
    _today = date.today()

    if interval == "1d":
        last_updated = sec.dailyupdate_data.all().first()
        _interval = Interval.DAILY
    elif interval == "1w":
        last_updated = sec.weeklyupdate_data.all().first()
        _interval = Interval.WEEKLY
    elif interval == "1mo":
        last_updated = sec.monthlyupdate_data.all().first()
        _interval = Interval.MONTHLY

    if last_updated is not None:
        print(f"last update: {last_updated.date}")
        if last_updated.date == _today:
            print("no update required, already updated today")
            messages.info(request, "Already up to date.")
            # forward to security overview page
            return HttpResponseRedirect(reverse("security", kwargs={"security_id": sec.id}))

    online_dao = Online_DAO_Factory().get_online_dao(sec.data_provider)

    # request new history from online dao
    result = online_dao.lookupHistory(security=sec, interval=_interval, look_back=5000)
    if len(result) > 10:

        try:
            with transaction.atomic():
                if interval == "1d":
                    # drop current history
                    Daily.objects.filter(security=sec).delete()
                    try:
                        DailyUpdate.objects.get(security=sec).delete()
                    except:
                        pass

                    # crate new history
                    Daily.objects.bulk_create(result)
                    DailyUpdate.objects.create(security=sec)
                    messages.info(request, "Daily history has been updated")
                elif interval == "1w":
                    # drop current history
                    Weekly.objects.filter(security=sec).delete()
                    try:
                        WeeklyUpdate.objects.get(security=sec).delete()
                    except:
                        pass

                    # crate new history
                    Weekly.objects.bulk_create(result)
                    WeeklyUpdate.objects.create(security=sec)
                    messages.info(request, "Weekly history has been updated")
                elif interval == "1mo":
                    # drop current history
                    Monthly.objects.filter(security=sec).delete()
                    try:
                        MonthlyUpdate.objects.get(security=sec).delete()
                    except:
                        pass

                    # crate new history
                    Monthly.objects.bulk_create(result)
                    MonthlyUpdate.objects.create(security=sec)
                    messages.info(request, "Monthly history has been updated")

        except DatabaseError as db_error:
            print(db_error)
            messages.warning(request, "Error while updating")

    # forward to security overview page
    return HttpResponseRedirect(reverse("security", kwargs={"security_id": sec.id}))


def technical_parameter(request, security_id) -> JsonResponse:
    sec = Security.objects.get(pk=security_id)

    if request.method == "POST":

        provided_data = json.loads(request.body)
        view = provided_data.get("view")
        
        data = {}
        data["view"] = view
        if view == "sd":
            
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

            data["tp_data"] = hurst_data
        elif view == "hurst":
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

            data["tp_data"] = hurst_data
        
        return JsonResponse(data, status=201)


def tech_analysis(request, security_id) -> JsonResponse:
    """
    generates a dictionary holding the current values for the different technical analysis parameter
    """

    sec = Security.objects.get(pk=security_id)
    data = {}
    if sec is None:
        data["error", "security has not been found"]
        return JsonResponse(data, status=404)
    
    sma50 = SMA(50)
    ema50 = EMA(50)
    ema20 = EMA(20)

    daily = sec.daily_data.all()[:1000]
    for entry in reversed(daily):
        close = float(entry.close)
        sma50.add(close)
        ema50_value = ema50.add(close)
        ema20_value = ema20.add(close)

    data["hurst"] = sma50.hurst()
    data["ema50"] = ema50_value
    data["ema20"] = ema20_value
    data["sd"] = sma50.sigma_delta()

    return JsonResponse(data, status=201)


def fundamental_analysis(request, security_id) -> JsonResponse:
    
    sec = Security.objects.get(pk=security_id)
    if sec is None:
        return JsonResponse({"error", "security has not been found"}, status=404)
    
    if sec.type == "EQUITY":
        online_dao = Online_DAO_Factory().get_online_dao(sec.data_provider)
        data = humanize_fundamentals(online_dao.lookup_financial_data(sec), online_dao.lookup_default_key_statistics(sec), online_dao.lookup_summary_detail(sec))
        return JsonResponse(data, status=201)
    else:
        return JsonResponse({"error":"no fundamental data available"}, status=404)

def security_history(request, security_id) -> JsonResponse:

    """
    POST: return a JsonResponse with a data dictionary holding:
        candle - ohlcv, Note: using the lookupPrice, we add the regular market as well
        EMA(50) and EMA(20)
    """

    if request.method == "POST":
        security = Security.objects.get(pk=security_id)
        data = {}
        if security is not None:

            data["currency_symbol"] = security.currency_symbol
        
            provided_data = json.loads(request.body)
            interval = provided_data.get("interval")
            data["interval"] = interval
            if interval == "d":
                history = security.daily_data.all()[:1000]
            elif interval == "w":
                history = security.weekly_data.all()[:1000]
            elif interval == "m":
                history = security.monthly_data.all()[:1000]
            else:
                data["error"] = "invalid interval"
                return JsonResponse(data, status=500)


            prices_data = list()
            ema50_data = list()
            ema50 = EMA(50)

            ema20_data = list()
            ema20 = EMA(20)

            bb = BollingerBands(20,2)
            bb_lower = list()
            bb_upper = list()

            volume_data = list()

            previous_close = 0
            for entry in reversed(history):
                # building the prices data using time and ohlc
                candle = {}
                candle["time"] = str(entry.date)
                candle["open"] = float(entry.open_price)
                candle["high"] = float(entry.high_price)
                candle["low"] = float(entry.low)
                candle["close"] = float(entry.close)
                prices_data.append(candle)

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
                
                volume_value = float(entry.volume)
                if volume_value > 0:
                    volume = {}
                    volume["time"] = str(entry.date)
                    volume["value"] = volume_value
                    if candle["close"] >= previous_close:
                        volume["color"] = RGB_GREEN
                    else:
                        volume["color"] = RGB_RED
                    volume_data.append(volume)

                bollinger = bb.add(float(entry.close))
                if bollinger is not None:
                    bb_lower_entry = {}
                    bb_lower_entry["time"] = str(entry.date)
                    bb_lower_entry["value"] = bollinger[0]

                    bb_upper_entry = {}
                    bb_upper_entry["time"] = str(entry.date)
                    bb_upper_entry["value"] = bollinger[1]

                    bb_lower.append(bb_lower_entry)
                    bb_upper.append(bb_upper_entry)

                previous_close = candle["close"]

            data["price"] = prices_data
            data["ema50"] = ema50_data
            data["ema20"] = ema20_data
            data["volume"] = volume_data
            data["bb_upper"] = bb_upper
            data["bb_lower"] = bb_lower
        else:
            data["error"] = "security not found"

        
        symbol = security.symbol
        dataProvider = security.data_provider
            
        # looking up additional information
        online_dao = Online_DAO_Factory().get_online_dao(dataProvider)

        price = online_dao.lookupPrice(symbol)
        time_ts = datetime.utcfromtimestamp(price["regularMarketTime"]).strftime("%Y-%m-%d")
        data["price"].append({"time": time_ts, "open": price["regularMarketOpen"]["raw"], "high": price["regularMarketDayHigh"]["raw"], "low": price["regularMarketDayLow"]["raw"], "close":price["regularMarketPrice"]["raw"]})
        status = 200
    else:
        data["error"] = "The resource was not found"
        status = 404

    return JsonResponse(data, status=status)

