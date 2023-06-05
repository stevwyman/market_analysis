from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from datetime import datetime, date
from data.technical_analysis import EMA, SMA, BollingerBands, MACD, RSI
from data.ai_helper import generate
from zoneinfo import ZoneInfo

from logging import getLogger

logger = getLogger(__name__)

import json
import time

from data.history_dao import History_DAO_Factory, Interval
from data.open_interest import (
    get_max_pain_history,
    next_expiry_date,
    update_data,
    generate_most_distribution,
    get_most_recent_distribution,
)
from .models import (
    User,
    Watchlist,
    Security,
    DataProvider,
    Daily,
    DailyUpdate,
    Weekly,
    WeeklyUpdate,
    Monthly,
    MonthlyUpdate,
    Limit,
)
from .forms import WatchlistForm, SecurityForm, LimitForm
from .helper import humanize_price, humanize_fundamentals


# Create your views here.

RGB_RED = "rgba(255,82,82, 0.8)"
RGB_GREEN = "rgba(0, 150, 136, 0.8)"


# main page get's rendered here
def index(request):
    return render(request, "data/index.html")


def start(request):
    cheats = list()

    # we use yahoo as we get near real time
    yahoo = DataProvider.objects.get(name="Yahoo")

    # we start for testing with only the DAX and the Dow Jones
    sec_2_watch = list()
    dax = Security.objects.get(data_provider=yahoo, symbol="^GDAXI")
    sec_2_watch.append(dax)
    djia = Security.objects.get(data_provider=yahoo, symbol="^DJI")
    sec_2_watch.append(djia)

    dao = History_DAO_Factory().get_online_dao(data_provider=yahoo)
    user = request.user

    for security in sec_2_watch:
        logger.debug(f"processing {security}")
        cheat = {}
        cheat["security"] = security
        # used for reference and % display
        price = dao.lookupPrice(security.symbol)
        current = price["regularMarketPrice"]["raw"]
        cheat["current"] = current

        entries = list()
        entries.append(
            {
                "name": "current",
                "value": current,
                "modifyable": False,
            }
        )

        daily = security.daily_data.all()[:400]

        # these are the predefined limits
        ema200 = EMA(200)
        ema200_value = 0
        ema50 = EMA(50)
        ema50_value = 0
        ema20 = EMA(20)
        ema20_value = 0
        bb = BollingerBands()
        bb_entry = None

        for entry in reversed(daily):
            ema200_value = ema200.add(float(entry.close))
            ema50_value = ema50.add(float(entry.close))
            ema20_value = ema20.add(float(entry.close))
            bb_entry = bb.add(float(entry.close))

        entries.append({"name": "ema(50)", "value": ema50_value, "delta": 100 * (ema50_value - current)/current, "modifyable": False})
        entries.append({"name": "ema(200)", "value": ema200_value, "delta": 100 * (ema200_value - current)/current, "modifyable": False})
        entries.append({"name": "ema(20)", "value": ema20_value, "delta": 100 * (ema20_value - current)/current, "modifyable": False})
        entries.append({"name": "bb upper", "value": bb_entry[1], "delta": 100 * (bb_entry[1] - current)/current, "modifyable": False})
        entries.append({"name": "bb lower", "value": bb_entry[0], "delta": 100 * (bb_entry[0] - current)/current, "modifyable": False})

        
        # user specific details
        limits = Limit.objects.filter(user=user, security=security).all()
        for limit in limits:
            entries.append(
                {
                    "name": limit.comment,
                    "value": limit.price,
                    "delta": 100 * (float(limit.price) - current)/current,
                    "modifyable": True,
                    "id": limit.id,
                }
            )

        cheat["entries"] = sorted(entries, key=lambda d: d["value"], reverse=True)
        cheat["ts"] = datetime.fromtimestamp(
            price["regularMarketTime"], ZoneInfo("America/New_York")
        )
        
        cheats.append(cheat)

    return render(request, "data/start.html", {"cheats": cheats})


def limit_new(request):

    # user requesting a new limit
    user = request.user

    if request.method == "GET":
        # show the page where the new limit can be created

        # the security for which a new limit shall be created
        try:
            security_id = request.GET.get("security_id")
            security = Security.objects.get(pk=security_id)
        except ObjectDoesNotExist:
            messages.warning(request, "Security not found")
            return HttpResponseRedirect(reverse("start"))
        
        form = LimitForm(initial={"user": user, "security": security})
        return render(request, "data/limit_new.html", {"form": form})
    else:
        # check the form and if valid, save it
        form = LimitForm(request.POST)
        if form.is_valid:
            form.save()
            messages.info(request, "Created new limit")
        else:
            logger.warn(form.errors.as_data())
            messages.error(request, "Could not create new limit")

        return HttpResponseRedirect(reverse("start"))


def limit_edit(request, limit_id):
    try:
        limit = Limit.objects.get(pk=limit_id)
    except ObjectDoesNotExist:
        messages.warning(request, "Limit not found")
        return HttpResponseRedirect(reverse("start"))

    if request.method == "POST":
        form = LimitForm(request.POST, instance=limit)
        if form.is_valid():
            # update the existing `limit` in the database
            form.save()
            # redirect to thestart page
            return HttpResponseRedirect(reverse("start"))
    # either if "GET" or not valid, show the edit page (again)
    form = LimitForm(instance=limit)
    return render(request, "data/limit_edit.html", {"form": form, "limit_id": limit.id})


def limit_drop(request, limit_id):
    try:
        limit = Limit.objects.get(pk=limit_id)
    except ObjectDoesNotExist:
        messages.warning(request, "Limit not found")
        return HttpResponseRedirect(reverse("start"))

    if request.method == "GET":
        limit.delete()
        messages.info(request, "Limit deleted")
        return HttpResponseRedirect(reverse("start"))


@login_required(login_url="login")
def watchlists(request):
    user = request.user
    watchlists = list()

    for watchlist in Watchlist.objects.filter(visibility="AU").all():
        watchlists.append(watchlist)

    for watchlist in Watchlist.objects.filter(user=user).all():
        watchlists.append(watchlist)

    if user.role != User.BASIC:
        for watchlist in Watchlist.objects.filter(visibility="AP").all():
            watchlists.append(watchlist)

    return render(request, "data/watchlists.html", {"watchlists": watchlists})


@login_required(login_url="login")
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


@login_required(login_url="login")
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


@login_required(login_url="login")
def watchlist(request, watchlist_id: int):
    watchlist = Watchlist.objects.get(pk=watchlist_id)
    securities = watchlist.securities.order_by("name").all()

    # building watchlist
    watchlist_entries = list()
    for security in securities:
        watchlist_entry = {}
        watchlist_entry["security"] = security
        dao = History_DAO_Factory().get_online_dao(security.data_provider)
        if security.data_provider.name == "Yahoo":
            watchlist_entry["price"] = humanize_price(dao.lookupPrice(security.symbol))
        else:
            history = security.daily_data.all()[:2]

            price = {}
            price["change_percent"] = (
                100 * (history[0].close - history[1].close) / history[1].close
            )
            price["price"] = history[0].close
            price["change"] = history[0].close - history[1].close

            price["timestamp"] = history[0].date
            watchlist_entry["price"] = price

        try:
            watchlist_entry["pe_forward"] = dao.lookup_summary_detail(security)[
                "forwardPE"
            ]["raw"]
        except:
            watchlist_entry["pe_forward"] = "-"

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

    logger.debug("sorting %s by %s" % (direction, order_by))

    if order_by == "change":
        watchlist_entries.sort(
            key=lambda x: x["price"]["change_percent"], reverse=_b_direction
        )
    elif order_by == "hurst":
        watchlist_entries.sort(key=lambda x: x["sma"]["hurst"], reverse=_b_direction)
    elif order_by == "spread":
        watchlist_entries.sort(key=lambda x: x["sma"]["sd"], reverse=_b_direction)
    elif order_by == "pef":
        watchlist_entries.sort(key=lambda x: x["pe_forward"], reverse=_b_direction)
    elif order_by == "delta":
        watchlist_entries.sort(key=lambda x: x["sma"]["delta"], reverse=_b_direction)

    # pagination
    paginator = Paginator(watchlist_entries, 6)
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
        {
            "watchlist": watchlist,
            "watchlist_entries": paged_watchlist_entries,
            "order_by": order_by,
            "direction": direction,
        },
    )


@login_required(login_url="login")
def security(request, security_id):
    """
    return a simple security entry with price
    """
    try:
        sec = Security.objects.get(pk=security_id)
    except:
        messages.warning(request, f"Security with id {security_id} could not be found.")
        return HttpResponseRedirect(reverse("index"))

    # looking up additional information
    online_dao = History_DAO_Factory().get_online_dao(sec.data_provider)
    price = online_dao.lookupPrice(sec.symbol)
    h_price = None
    if sec.data_provider.name == "Yahoo":
        h_price = humanize_price(price)
    else:
        history = sec.daily_data.all()[:2]

        h_price = {}
        h_price["change_percent"] = (
            100 * (history[0].close - history[1].close) / history[1].close
        )
        h_price["price"] = history[0].close
        h_price["change"] = history[0].close - history[1].close

        h_price["timestamp"] = history[0].date

    # for testing
    """
    if price["quoteType"] == "EQUITY":
        quoteSummary = online_dao.lookup_financial_data(sec)
    else:
        quoteSummary = {}
    """

    return render(
        request,
        "data/security.html",
        {
            "security": sec,
            "price": h_price,
            # for testing
            # "quote_summary": quoteSummary
        },
    )


@login_required(login_url="login")
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
            online_dao = History_DAO_Factory().get_online_dao(dataProvider)

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
            if summaryProfile is not None:
                try:
                    sec.country = summaryProfile["country"]
                    sec.industry = summaryProfile["industry"]
                    sec.sector = summaryProfile["sector"]
                except:
                    if "error" in summaryProfile.keys():
                        messages.warning(request, summaryProfile["error"])
                    else:
                        messages.warning(
                            request,
                            "no valid data for 'country, 'industry', or 'sector' ",
                        )

            sec.save()
            watchlist.securities.add(sec)

            #
            # add initial history for this entry
            #
            online_dao = History_DAO_Factory().get_online_dao(sec.data_provider)

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
                    if (
                        e
                        == "Security with this Symbol and Data provider already exists."
                    ):
                        sec = Security.objects.get(
                            symbol=form.data["symbol"],
                            data_provider=form.data["data_provider"],
                        )
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


@login_required(login_url="login")
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


@login_required(login_url="login")
def security_search(request) -> JsonResponse:
    data = {}

    if request.method == "POST":
        query = request.POST["id"]

        results = list()
        securities = Security.objects.filter(
            Q(name__contains=query) | Q(symbol__contains=query)
        )
        logger.info(f"found {securities.count()} entries for {query}")

        if securities.count() == 1:
            # go directly to the identified security
            security = securities.first()
            return HttpResponseRedirect(
                reverse("security", kwargs={"security_id": security.id})
            )

        else:
            if securities.count() == 0:
                messages.warning(request, "could not find a matching security")
            else:
                watchlist_entries = list()
                for security in securities:
                    watchlist_entry = {}
                    watchlist_entry["security"] = security
                    dao = History_DAO_Factory().get_online_dao(security.data_provider)
                    if security.data_provider.name == "Yahoo":
                        watchlist_entry["price"] = humanize_price(
                            dao.lookupPrice(security.symbol)
                        )

                    try:
                        watchlist_entry["pe_forward"] = dao.lookup_summary_detail(
                            security
                        )["forwardPE"]["raw"]
                    except:
                        watchlist_entry["pe_forward"] = "-"

                    try:
                        history = security.daily_data.all()[:55]
                        watchlist_entry["sma"] = SMA(50).latest(history)
                    except ValueError as va:
                        messages.warning(request, va)

                    watchlist_entries.append(watchlist_entry)

                return render(
                    request,
                    "data/watchlist.html",
                    {
                        "watchlist_entries": watchlist_entries,
                    },
                )


@login_required(login_url="login")
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
            return HttpResponseRedirect(
                reverse("security", kwargs={"security_id": sec.id})
            )

    online_dao = History_DAO_Factory().get_online_dao(sec.data_provider)

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


@login_required(login_url="login")
def technical_parameter(request, security_id) -> JsonResponse:
    """
    generate data for charting of technical charts, i.e. sigma/delta, hurst ...
    """
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
                    sd_entry["time"] = str(entry.date)
                    sd_entry["value"] = sd_value
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
                    sd_entry["time"] = str(entry.date)
                    sd_entry["value"] = sma50.hurst()
                    hurst_data.append(sd_entry)

            data["tp_data"] = hurst_data

        logger.debug(data)

        return JsonResponse(data, status=201)


@login_required(login_url="login")
def tech_analysis(request, security_id) -> JsonResponse:
    """
    generates a dictionary holding the current values for the different technical analysis parameter
    TODO: RSI, MACD
    """

    sec = Security.objects.get(pk=security_id)
    data = {}
    if sec is None:
        data["error", "security has not been found"]
        return JsonResponse(data, status=404)

    sma50 = SMA(50)
    ema50 = EMA(50)
    ema20 = EMA(20)

    macd = MACD()
    rsi = RSI()
    bb = BollingerBands()

    daily = sec.daily_data.all()[:1000]
    for entry in reversed(daily):
        close = float(entry.close)
        sma50.add(close)
        ema50_value = ema50.add(close)
        ema20_value = ema20.add(close)
        macd_value = macd.add(close)
        rsi_value = rsi.add(close)
        bb_value = bb.add(close)

    # data[f"EMA(50)[{sec.currency_symbol}]"] = ema50_value
    data["δEMA(50)[%]"] = 100 * (close - ema50_value) / ema50_value
    # data[f"EMA(20)[{sec.currency_symbol}]"] = ema20_value
    data["δEMA(20)[%]"] = 100 * (close - ema20_value) / ema20_value
    data["MACD <sub>Histogram</sub>"] = macd_value[2]
    data["RSI"] = rsi_value
    data["MA(50) spread"] = sma50.sigma_delta()

    bb_center = (bb_value[0] + bb_value[1]) / 2
    bb_position_rel = close - bb_center
    if bb_position_rel >= 0:  # we are in the upper band
        data["BBands"] = 100 * bb_position_rel / (bb_value[1] - bb_center)
    else:
        data["BBands"] = -100 * bb_position_rel / (bb_value[0] - bb_center)

    hurst_value = sma50.hurst()
    if hurst_value > 0.5:
        data["Hurst<sub>trending</sub>"] = hurst_value
    else:
        data["Hurst<sub>mean rev.</sub>"] = hurst_value

    return JsonResponse(data, status=201)


@login_required(login_url="login")
def fundamental_analysis(request, security_id) -> JsonResponse:
    """
    currently only the data is shown, in a next step we could show the reference by sector as well
    """
    sec = Security.objects.get(pk=security_id)
    if sec is None:
        return JsonResponse({"error", "security has not been found"}, status=404)

    if sec.type == "EQUITY":
        online_dao = History_DAO_Factory().get_online_dao(sec.data_provider)
        data = humanize_fundamentals(
            online_dao.lookup_financial_data(sec),
            online_dao.lookup_default_key_statistics(sec),
            online_dao.lookup_summary_detail(sec),
        )
        return JsonResponse(data, status=201)
    else:
        return JsonResponse({"error": "no fundamental data available"}, status=404)


@login_required(login_url="login")
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

            bb = BollingerBands()
            bb_lower = list()
            bb_upper = list()

            macd = MACD()
            macd_history_data = list()

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

                macd_value = macd.add(float(entry.close))
                if macd_value is not None:
                    macd_histo_entry = {}
                    macd_histo_entry["time"] = str(entry.date)
                    macd_histo_entry["value"] = macd_value[2]

                    macd_history_data.append(macd_histo_entry)

                previous_close = candle["close"]

            data["price"] = prices_data
            data["ema50"] = ema50_data
            data["ema20"] = ema20_data
            data["volume"] = volume_data
            data["macd"] = macd_history_data
            data["bb_upper"] = bb_upper
            data["bb_lower"] = bb_lower
        else:
            data["error"] = "security not found"

        symbol = security.symbol
        dataProvider = security.data_provider

        if dataProvider.name == "Yahoo":
            # looking up additional information
            online_dao = History_DAO_Factory().get_online_dao(dataProvider)

            price = online_dao.lookupPrice(symbol)
            time_ts = datetime.utcfromtimestamp(price["regularMarketTime"]).strftime(
                "%Y-%m-%d"
            )
            data["price"].append(
                {
                    "time": time_ts,
                    "open": price["regularMarketOpen"]["raw"],
                    "high": price["regularMarketDayHigh"]["raw"],
                    "low": price["regularMarketDayLow"]["raw"],
                    "close": price["regularMarketPrice"]["raw"],
                }
            )

        status = 200
    else:
        data["error"] = "The resource was not found"
        status = 404

    return JsonResponse(data, status=status)


@login_required(login_url="login")
def update_all(request):
    data = {}

    all_securities = Security.objects.all()
    for security in all_securities:
        _today = date.today()
        last_updated = security.dailyupdate_data.all().first()

        if last_updated is not None:
            if last_updated.date == _today:
                logger.info(f"no update required for {security}")
                continue

        if security.data_provider.name != "Yahoo":
            continue

        online_dao = History_DAO_Factory().get_online_dao(security.data_provider)

        # request new history from online dao
        result = online_dao.lookupHistory(security=security, look_back=5000)
        if len(result) > 10:
            try:
                with transaction.atomic():
                    # drop current history
                    Daily.objects.filter(security=security).delete()
                    try:
                        DailyUpdate.objects.get(security=security).delete()
                    except:
                        pass

                    # crate new history
                    Daily.objects.bulk_create(result)
                    DailyUpdate.objects.create(security=security)
                    logger.info(f"Daily history has been updated for {security.symbol}")

            except DatabaseError as db_error:
                logger.error(db_error)

        time.sleep(5)

    return JsonResponse(data, status=200)


import pandas as pd


@login_required(login_url="login")
def build_data_set(request) -> JsonResponse:
    """
    building a data structure that can be used as input for an AI algorithm
    """

    # all_securities = Security.objects.all()
    # all_securities = Security.objects.filter(symbol="ADS.DE")
    all_securities = Watchlist.objects.get(name="DAX").securities.all()

    dataframe = generate(all_securities)
    compression_opts = dict(method="zip", archive_name="out.csv")
    dataframe.to_csv("dax.zip", index=False, compression=compression_opts)

    response_data = {}
    response_data["lines"] = len(dataframe)
    return JsonResponse(response_data, status=200)


#
# section for open interest
#
underlyings = {
    "COVESTRO": {"name": "Covestro", "productId": 47410, "productGroupId": 9772},
    "ADIDAS": {"name": "Addidas", "productId": 47634, "productGroupId": 9772},
    "ALLIANZ": {"name": "Allianz", "productId": 47910, "productGroupId": 9772},
    "DAX": {"name": "DAX perf.", "productId": 70044, "productGroupId": 13394},
    "ES50": {"name": "Euro STOXX 50", "productId": 69660, "productGroupId": 13370},
    "EBF": {"name": "Euro Bund Future", "productId": 70050, "productGroupId": 13328},
}


@login_required(login_url="login")
def open_interest(request, underlying: str):
    if underlying in underlyings.keys():
        product = underlyings[underlying]
        expiry_date = next_expiry_date()
        parameter = {"product": product, "expiry_date": expiry_date}
        max_pain_over_time = sorted(
            get_max_pain_history(parameter), key=lambda x: x[0], reverse=True
        )
        most_recent = {}
        if len(max_pain_over_time) > 0:
            latest = max_pain_over_time[0]
            most_recent["ts"] = latest[0]
            most_recent["strike"] = latest[1]
        else:
            messages.warning(request, "no data found")
    else:
        messages.error(request, "Underlying not found")
        return HttpResponseRedirect(reverse("watchlists"))

    # using POST for requesting an update of data
    if request.method == "POST":
        messages.info(request, "Data has been updated")
        update_data(parameter)
        return HttpResponseRedirect(
            reverse("open_interest", kwargs={"underlying": underlying})
        )

    return render(
        request,
        "data/open_interest.html",
        {
            "underlying": underlying,
            "product": product,
            "latest": most_recent,
            "underlyings": underlyings,
        },
    )


@login_required(login_url="login")
def max_pain(request, underlying: str) -> JsonResponse:
    """
    returning a (time:value) dictionary showing the maxpain value by date
    """
    data = {}
    if underlying in underlyings.keys():
        product = underlyings[underlying]
    else:
        data["error"] = "underlying not found"
        return JsonResponse(data, status=404)

    expiry_date = next_expiry_date()
    parameter = {"product": product, "expiry_date": expiry_date}

    logger.info(parameter)

    max_pain_over_time = sorted(
        get_max_pain_history(parameter), key=lambda x: x[0], reverse=False
    )

    mp = list()

    for max_pain in max_pain_over_time:
        entry = {}
        entry["time"] = max_pain[0]
        entry["value"] = max_pain[1]
        mp.append(entry)

    data["max_pain"] = mp

    return JsonResponse(data, status=200)


@login_required(login_url="login")
def max_pain_distribution(request, underlying: str) -> JsonResponse:
    """
    returning a dataset showing the distribution over strikes for a specific day
    """
    data = {}
    if underlying in underlyings.keys():
        product = underlyings[underlying]
    else:
        data["error"] = "underlying not found"
        return JsonResponse(data, status=404)

    expiry_date = next_expiry_date()
    parameter = {"product": product, "expiry_date": expiry_date}

    distribution = get_most_recent_distribution(parameter)

    return JsonResponse(distribution, status=200)


#
# section for finra-bonds
#
from data.corp_bonds import update, read_bonds_data

bonds = {"hy": "High Yield", "ig": "Investment Grade"}


# @login_required(login_url="login")
def corp_bonds(request):
    """
    for a get request, share the latest data
    for a POST request, update the data
    """

    # using POST for requesting an update of data
    if request.method == "POST":
        logger.info("request to update the bond data")
        update()
        messages.info(request, "Data has been updated")
        return HttpResponseRedirect(reverse("corp_bonds"))
    else:
        data = {}
        data["title"] = bonds["hy"]
        ad = read_bonds_data(bonds["hy"])
        data["ad_data"] = ad

        return render(request, "data/corp_bonds.html", data)


@login_required(login_url="login")
def corp_bonds_data(request, type: str) -> JsonResponse:
    """
    returning a (time:value) dictionary showing the data specified by the 'type' (a-d line) value by date
    using the bonds dictionary to define the available types
    """
    data = read_bonds_data(bonds[type])

    return JsonResponse(data, status=200)


#
# managing participants
#


def login_view(request):
    if request.method == "POST":
        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("start"))
        else:
            return render(
                request,
                "data/login.html",
                {"message": "Invalid username and/or password."},
            )
    else:
        return render(request, "data/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(
                request, "data/register.html", {"message": "Passwords must match."}
            )

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.role = User.BASIC
            user.save()
        except IntegrityError:
            return render(
                request, "data/register.html", {"message": "Username already taken."}
            )
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "data/register.html")


#
# init the default watchlists
#
from data.indices import DATA


@login_required(login_url="login")
def create_default_lists(request):
    """
    simple action to initialize the database with a hand full of indices
    """

    try:
        admin = User.objects.get(username="myAdmin")
    except ObjectDoesNotExist:
        admin = User(username="myAdmin", email="admin@admin.de", password="_admin-123")
        admin.role = 1
        admin.save()
        print(f"User {admin} created")

    try:
        data_provider = DataProvider.objects.get(name="Yahoo")
    except ObjectDoesNotExist:
        data_provider = DataProvider(
            name="Yahoo", description="Provider for finance.yahoo.com"
        )
        data_provider.save()
        print(f"Data provider {data_provider} created")

    # looking up additional information
    online_dao = History_DAO_Factory().get_online_dao(data_provider)

    for entry in DATA:
        name = DATA[entry]["name"]
        list = DATA[entry]["list"]

        # create watchlist
        try:
            watchlist = Watchlist.objects.get(name=name)
            continue
        except ObjectDoesNotExist:
            watchlist = Watchlist(name=name, user=admin, visibility="AP")
            watchlist.save()
            print(f"created {watchlist}")

        # add securities to watchlist
        for symbol in list:
            price = online_dao.lookupPrice(symbol)

            # create new Security
            try:
                sec = Security.objects.get(symbol=symbol, data_provider=data_provider)
                watchlist.securities.add(sec)
                print(f"added {sec} to {watchlist}")
                continue
            except ObjectDoesNotExist:
                logger.info("Processing " + symbol)

            sec = Security(symbol=symbol, data_provider=data_provider)
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
                pass

            sec.save()
            watchlist.securities.add(sec)
            print(f"added {sec} to {watchlist}")

    return JsonResponse({"status": "all done"}, status=201)


from data.sp500_helper import import_sp500


@login_required(login_url="login")
def create_sp500_list(request):
    import_sp500()
    return JsonResponse({"status": "all done"}, status=201)
