from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from datetime import datetime, date
from data.technical_analysis import EMA, SMA, BollingerBands, MACD, RSI, Ichimoku, evaluate_ikh
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
from .helper import humanize_price, humanize_fundamentals, generate_intraday_image, generate_max_pain_distribution

from typing import List, Dict

# Create your views here.

RGB_RED = "rgba(255,82,82, 0.8)"
RGB_GREEN = "rgba(0, 150, 136, 0.8)"

# some decorators for user role management


def is_premium(user) -> bool:
    """
    checks if the user is at least premium
    """
    return True if user.role < 3 else False


def is_manager(user) -> bool:
    """
    checks if the user is at least manager
    """
    return True if user.role < 2 else False


# main page get's rendered here
def index(request):
    return render(request, "data/index.html")


@login_required()
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
        cheat = dict()
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

        entries.append(
            {
                "name": "ema(50)",
                "value": ema50_value,
                "delta": 100 * (ema50_value - current) / current,
                "modifyable": False,
            }
        )
        entries.append(
            {
                "name": "ema(200)",
                "value": ema200_value,
                "delta": 100 * (ema200_value - current) / current,
                "modifyable": False,
            }
        )
        entries.append(
            {
                "name": "ema(20)",
                "value": ema20_value,
                "delta": 100 * (ema20_value - current) / current,
                "modifyable": False,
            }
        )
        entries.append(
            {
                "name": "bb upper",
                "value": bb_entry[1],
                "delta": 100 * (bb_entry[1] - current) / current,
                "modifyable": False,
            }
        )
        entries.append(
            {
                "name": "bb lower",
                "value": bb_entry[0],
                "delta": 100 * (bb_entry[0] - current) / current,
                "modifyable": False,
            }
        )

        # user specific details
        limits = Limit.objects.filter(user=user, security=security).all()
        for limit in limits:
            entries.append(
                {
                    "name": limit.comment,
                    "value": limit.price,
                    "delta": 100 * (float(limit.price) - current) / current,
                    "modifyable": True,
                    "id": limit.id,
                }
            )

        cheat["entries"] = sorted(entries, key=lambda d: d["value"], reverse=True)
        cheat["ts"] = datetime.fromtimestamp(
            price["regularMarketTime"], ZoneInfo("America/New_York")
        )

        cheats.append(cheat)

    # intraday images
    dax_intraday = cache.get_or_set("dax_intraday", generate_intraday_image(14097793), 120)
    vdax_intraday = cache.get_or_set("vdax_intraday", generate_intraday_image(12105789), 120)
    djia_intraday = cache.get_or_set("djia_intraday", generate_intraday_image(13320013), 120)

    return render(request, "data/start.html", {"cheats": cheats, "dax_intraday": dax_intraday, "vdax_intraday": vdax_intraday, "djia_intraday": djia_intraday})


@login_required()
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


@login_required()
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


@login_required()
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


@login_required()
def watchlists(request):
    user = request.user
    watchlists = list()

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

    return render(request, "data/watchlists.html", {"watchlists": watchlists})


@login_required()
@user_passes_test(is_premium, login_url="start")
def watchlist_new(request):
    if request.method == "GET":
        user = request.user
        form = WatchlistForm(initial={"user": user})
        return render(request, "data/watchlist_new.html", {"form": form})
    else:
        form = WatchlistForm(request.POST)
        if form.is_valid:
            form.save()
            messages.info(request, "Created new watchlist")
        else:
            logger.error(form.errors.as_data())
            messages.error(request, "Could not create new watchlist")

        return HttpResponseRedirect(reverse("watchlists"))


@login_required()
@user_passes_test(is_premium, login_url="start")
def watchlist_edit(request, watchlist_id):
    try:
        user = request.user
        watchlist = Watchlist.objects.get(user=user, pk=watchlist_id)
    except ObjectDoesNotExist:
        messages.warning(request, "Watchlist not found")
        return HttpResponseRedirect(reverse("watchlists"))

    if request.method == "POST":
        form = WatchlistForm(request.POST, instance=watchlist)
        if form.is_valid():
            # update the existing `limit` in the database
            form.save()
            # redirect to watchlists page
            return HttpResponseRedirect(reverse("watchlists"))

    # either if "GET" or not valid, show the edit page (again)
    form = WatchlistForm(instance=watchlist)
    return render(
        request,
        "data/watchlist_edit.html",
        {"form": form, "watchlist_id": watchlist.id},
    )


@login_required()
@user_passes_test(is_premium, login_url="start")
def watchlist_drop(request, watchlist_id):
    """
    remove the watchlist
    """
    user = request.user
    try:
        watchlist = Watchlist.objects.get(user=user, pk=watchlist_id)
        watchlist.delete()
        messages.info(request, "Watchlist dropped")
    except ObjectDoesNotExist:
        messages.warning(request, "Watchlist not found")

    return HttpResponseRedirect(reverse("watchlists"))


@login_required()
def watchlist(request, watchlist_id: int):
    watchlist = Watchlist.objects.get(pk=watchlist_id)
    securities = watchlist.securities.order_by("name").all()

    # building watchlist
    watchlist_entries = list()
    for security in securities:
        
        # try to get the entry from the cache
        watchlist_entry = cache.get(security.pk)

        # if not already in the cache, crete new
        if watchlist_entry is None:
            watchlist_entry = dict()

            watchlist_entry["security"] = security
            dao = History_DAO_Factory().get_online_dao(security.data_provider)
            history = security.daily_data.all()[:200]
            
            if security.data_provider.name == "Yahoo":
                watchlist_entry["price"] = humanize_price(dao.lookupPrice(security.symbol))
            else:
                
                price = dict()
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
                watchlist_entry["pe_forward"] = float("nan")

            try:
                ikh = Ichimoku()
                sma = SMA(50)
                for h in reversed(history):
                    close = float(h.close)
                    ikh_entry = ikh.add(high=float(h.high_price), low=float(h.low), close=close)
                    sma_entry = sma.add(close)
                    sd_entry = sma.sigma_delta()
                    hurst_entry = sma.hurst()
                    
                watchlist_entry["ikh_evaluation"] = evaluate_ikh(close, ikh_entry)
                watchlist_entry["sma"] = {
                    "hurst": hurst_entry, 
                    "sd": sd_entry,
                    "delta": 100 * (close - sma_entry) / sma_entry
                    }              
            except ValueError as va:
                messages.warning(request, va)

            cache.add(security.pk, watchlist_entry, 300)
        
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
    elif order_by == "ikh":
        watchlist_entries.sort(key=lambda x: x["ikh_evaluation"], reverse=_b_direction)

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


@login_required()
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


@login_required()
def security_new(request, watchlist_id):
    user = request.user
    watchlist = Watchlist.objects.get(user=user, pk=watchlist_id)
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
                    logger.error(db_error)
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

            logger.warn(form.errors.as_data())  # here you print errors to terminal
            messages.error(request, "Form is not valid")

        return HttpResponseRedirect(
            reverse("watchlist", kwargs={"watchlist_id": watchlist.id})
        )


@login_required()
@user_passes_test(is_premium, login_url="start")
def security_drop(request, security_id):
    """
    remove the security from the given watchlist and if no other holds a reference, drop the security and the elated data
    """
    watchlist = Watchlist.objects.get(pk=security_id)
    if request.method == "POST":
        security_id = request.POST.get("security_id", "")
        security = Security.objects.get(pk=security_id)
        watchlist.securities.remove(security)

        related_watchlists = security.watchlists.all()
        if related_watchlists.count() == 0:
            security.delete()
            logger.info(f"removed {security_id}")

    return HttpResponseRedirect(
        reverse("watchlist", kwargs={"watchlist_id": watchlist.id})
    )


@login_required()
def security_search(request) -> JsonResponse:
    query = request.POST["id"]
    if len(query) < 3:
        messages.warning(request, "provide more letters for a search")
        return HttpResponseRedirect(reverse("start"))

    if request.method == "POST":
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
                return HttpResponseRedirect(reverse("start"))
            else:
                watchlist_entries: List = list()
                for security in securities:
                    watchlist_entry: Dict = dict()
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


@login_required()
@user_passes_test(is_premium, login_url="start")
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
        logger.debug(f"last update: {last_updated.date}")
        if last_updated.date == _today:
            logger.debug("no update required, already updated today")
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
            logger.warn(db_error)
            messages.warning(request, "Error while updating")

    # forward to security overview page
    return HttpResponseRedirect(reverse("security", kwargs={"security_id": sec.id}))


@login_required()
def technical_parameter(request, security_id) -> JsonResponse:
    """
    generate data for charting of technical charts, i.e. sigma/delta, hurst ...
    """
    sec = Security.objects.get(pk=security_id)

    if request.method == "POST":
        provided_data = json.loads(request.body)
        view = provided_data.get("view")

        data: Dict = dict()
        data["view"] = view
        if view == "sd":
            daily = sec.daily_data.all()[:1000]

            hurst_data = list()
            sma50 = SMA(50)

            for entry in reversed(daily):
                sma50.add(float(entry.close))
                sd_value = sma50.sigma_delta()
                if sd_value is not None:
                    hurst_data.append({"time": str(entry.date), "value": sd_value})

            data["tp_data"] = hurst_data
        elif view == "hurst":
            daily = sec.daily_data.all()[:400]

            hurst_data = list()
            sma50 = SMA(50)

            for entry in reversed(daily):
                sma50.add(float(entry.close))
                hurst_value = sma50.hurst()
                if hurst_value is not None:
                    hurst_data.append({"time": str(entry.date), "value": hurst_value})

            data["tp_data"] = hurst_data
        elif view == "ikh":
            daily = sec.daily_data.all()[:400]

            ikh_data = list()
            ichimoku = Ichimoku()

            for entry in reversed(daily):
                ichimoku_entry = ichimoku.add(high=float(entry.open),
                             low=float(entry.low),
                              close=float(entry.close) )
                
                if ichimoku_entry is not None:
                    ikh_data.append({"time":str(entry.date), "ikh": ichimoku_entry})
                data["tp_data"] = ikh_data

        logger.debug(data)

        return JsonResponse(data, status=201)


@login_required()
def tech_analysis(request, security_id) -> JsonResponse:
    """
    generates a dictionary holding the current values for the different technical analysis parameter
    """

    sec = Security.objects.get(pk=security_id)
    data: Dict = dict()
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

    if ema50_value is not None:
        data["δEMA(50)[%]"] = 100 * (close - ema50_value) / ema50_value

    if ema20_value is not None:
        data["δEMA(20)[%]"] = 100 * (close - ema20_value) / ema20_value

    if macd_value is not None:
        data["MACD <sub>Histogram</sub>"] = macd_value[2]

    if rsi_value is not None:
        data["RSI"] = rsi_value

    sma50_sigma_delta = sma50.sigma_delta()
    if sma50_sigma_delta is not None:
        data["MA(50) spread"] = sma50_sigma_delta

    if bb_value is not None:
        bb_center = (bb_value[0] + bb_value[1]) / 2
        bb_position_rel = close - bb_center
        if bb_position_rel >= 0:  # we are in the upper band
            data["BBands"] = 100 * bb_position_rel / (bb_value[1] - bb_center)
        else:
            data["BBands"] = -100 * bb_position_rel / (bb_value[0] - bb_center)

    sma50_hurst = sma50.hurst()
    if sma50_hurst is not None:
        if sma50_hurst > 0.5:
            data["Hurst<sub>trending</sub>"] = sma50_hurst
        else:
            data["Hurst<sub>mean rev.</sub>"] = sma50_hurst

    return JsonResponse(data, status=201)


@login_required()
def fundamental_analysis(request, security_id) -> JsonResponse:
    """
    currently only the data is shown, in a next step we could show the reference by sector as well
    """
    sec = Security.objects.get(pk=security_id)
    if sec is None:
        return JsonResponse({"error", "security has not been found"}, status=404)

    if sec.type == "EQUITY" and sec.data_provider.name == "Yahoo":
        online_dao = History_DAO_Factory().get_online_dao(sec.data_provider)
        data = humanize_fundamentals(
            online_dao.lookup_financial_data(sec),
            online_dao.lookup_default_key_statistics(sec),
            online_dao.lookup_summary_detail(sec),
        )
        return JsonResponse(data, status=201)
    else:
        return JsonResponse({"error": "no fundamental data available"}, status=404)


@login_required()
def security_history(request, security_id) -> JsonResponse:
    """
    POST: return a JsonResponse with a data dictionary holding:
        candle - ohlcv, Note: using the lookupPrice, we add the regular market as well
        EMA(50) and EMA(20)
    """
    data: Dict = dict()

    if request.method == "POST":
        security = Security.objects.get(pk=security_id)

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

            previous_close: float = 0
            for entry in reversed(history):
                close = float(entry.close)
                # building the prices data using time and ohlc
                prices_data.append(
                    {
                        "time": str(entry.date),
                        "open": float(entry.open_price),
                        "high": float(entry.high_price),
                        "low": float(entry.low),
                        "close": close,
                    }
                )

                ema50_value = ema50.add(close)
                if ema50_value is not None:
                    ema50_data.append({"time": str(entry.date), "value": ema50_value})

                ema20_value = ema20.add(close)
                if ema20_value is not None:
                    ema20_data.append({"time": str(entry.date), "value": ema20_value})

                volume_value = float(entry.volume)
                if volume_value > 0:
                    volume_data.append(
                        {
                            "time": str(entry.date),
                            "value": volume_value,
                            "color": RGB_GREEN if close >= previous_close else RGB_RED,
                        }
                    )

                bollinger = bb.add(close)
                if bollinger is not None:
                    bb_lower.append({"time": str(entry.date), "value": bollinger[0]})
                    bb_upper.append({"time": str(entry.date), "value": bollinger[1]})

                macd_value = macd.add(close)
                if macd_value is not None:
                    macd_history_data.append(
                        {"time": str(entry.date), "value": macd_value[2]}
                    )

                previous_close = close

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


@login_required()
@user_passes_test(is_manager, login_url="start")
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


@login_required()
@user_passes_test(is_manager, login_url="start")
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


@login_required()
@user_passes_test(is_premium, login_url="start")
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


    ## for testing
    distribution_image = generate_max_pain_distribution(parameter)

    return render(
        request,
        "data/open_interest.html",
        {
            "underlying": underlying,
            "product": product,
            "latest": most_recent,
            "underlyings": underlyings,
            #
            "distribution": distribution_image
        },
    )


@login_required()
@user_passes_test(is_premium, login_url="start")
def max_pain_history(request, underlying: str) -> JsonResponse:
    """
    returning a (time:value) dictionary showing the maxpain value by date
    """
    data: Dict = dict()
    if underlying in underlyings.keys():
        product = underlyings[underlying]
    else:
        data["error"] = "underlying not found"
        return JsonResponse(data, status=404)

    expiry_date = next_expiry_date()
    parameter = {"product": product, "expiry_date": expiry_date}

    logger.debug(parameter)

    max_pain_over_time = sorted(
        get_max_pain_history(parameter), key=lambda x: x[0], reverse=False
    )

    mp: List = list()

    for max_pain in max_pain_over_time:
        entry = {}
        entry["time"] = max_pain[0]
        entry["value"] = max_pain[1]
        mp.append(entry)

    data["max_pain"] = mp

    return JsonResponse(data, status=200)


@login_required()
@user_passes_test(is_premium, login_url="start")
def max_pain_distribution(request, underlying: str) -> JsonResponse:
    """
    returning an image showing the most recent distribution over strikes 
    """

    if underlying in underlyings.keys():
        product = underlyings[underlying]
        expiry_date = next_expiry_date()
        parameter = {"product": product, "expiry_date": expiry_date}
    else:
        messages.error(request, "Underlying not found")
        return HttpResponseRedirect(reverse("watchlists"))

    distribution = generate_max_pain_distribution(parameter)
    data = {"distribution": distribution}

    return JsonResponse(data, status=200)


#
# section for finra-bonds
#
from data.corp_bonds import update, read_bonds_data

bonds = {"hy": "High Yield", "ig": "Investment Grade"}


# @login_required()
@user_passes_test(is_premium, login_url="start")
def corp_bonds(request):
    """
    for a get request, share the latest data
    for a POST request, update the data
    """

    # using POST for requesting an update of data
    if request.method == "POST":
        logger.info("request to update the bond data")
        try:
            count = update()
            messages.info(request, f"{count} entries have been updated")
        except:
            messages.warning(request, "Could not update bond data")
        return HttpResponseRedirect(reverse("corp_bonds"))
    else:

        hy_ad = read_bonds_data(bonds["hy"])["ad"]
        hy_trend = read_bonds_data(bonds["hy"])["trend"]

        ig_ad = read_bonds_data(bonds["ig"])["ad"]
        ig_trend = read_bonds_data(bonds["ig"])["trend"]

        data = {
            "hy_time": hy_ad[-1]["date"], 
            "hy_value": hy_ad[-1]["value"],
            "hy_trend": hy_trend[-1]["value"],
            "ig_time": ig_ad[-1]["time"], 
            "ig_value": ig_ad[-1]["value"],
            "ig_trend": ig_trend[-1]["value"]
            }
        
        return render(request, "data/corp_bonds.html", {"data":data})


@login_required()
@user_passes_test(is_premium, login_url="start")
def corp_bonds_data(request, type: str) -> JsonResponse:
    """
    returning a (time:value) dictionary showing the data specified by the 'type' (a-d line) value by date
    using the bonds dictionary to define the available types
    """
    data = read_bonds_data(bonds[type])

    return JsonResponse(data, status=200)


#
# section for sentiment
#
sources = {"FRA": "Sentiment at Frankfurt",
           "AAII": "Private investors in the US",
           "NAAIM": "Portfolio exposure from professionals in the US",
           "FRA_SPREAD": "Shows the difference in bull/bear spread for privates and institutionals"}

@login_required
def sentiment(request):

    try:
        data_provider = DataProvider.objects.get(name="wyca-analytics")
    except ObjectDoesNotExist:
        data_provider = DataProvider.objects.create(name="wyca-analytics")

    sentiment_dao = History_DAO_Factory().get_online_dao(data_provider)

    if request.method == "GET":
        try:
            fra = json.loads(sentiment_dao.lookupData("FRA", 2))
            aaii = json.loads(sentiment_dao.lookupData("AAII", 2))
            naaim = json.loads(sentiment_dao.lookupData("NAAIM", 2))
        except:
            messages.warning(request, "Could not get data from source")
            return render(request, "data/index.html")

        return render(request, "data/sentiment.html", {"fra": fra, "aaii": aaii, "naaim": naaim})

    elif request.method == "POST":

        data: Dict = dict()

        provided_data = json.loads(request.body)
        source = provided_data.get("source", "NAAIM")
        size = provided_data.get("size", 200)

        if source not in sources:
            data["error"] = "Invalid parameter provided"
            return JsonResponse(data, status=201)
        
        data["source"] = source

        if source == "NAAIM":
            naaim_data = list()
            try: 
                naaim = json.loads(sentiment_dao.lookupData("NAAIM", size))
                for entry in naaim["exposures"]:
                    naaim_data.append({"time": entry["date"], "value": entry["mean"]})
                data["naaim_exposure"] = naaim_data
            except:
                data["error"] = "no connection"
                return JsonResponse(data, status=401)
        elif source == "AAII":
            aaii_bulls = list()
            aaii_bears = list()
            try:
                aaii = json.loads(sentiment_dao.lookupData("AAII", size))
                for entry in aaii["aaii"]:
                    aaii_bulls.append({"time": entry["date"], "value": entry["bull"]})
                    aaii_bears.append({"time": entry["date"], "value": entry["bear"]})
                data["aaii_bulls"] = aaii_bulls
                data["aaii_bears"] = aaii_bears
            except:
                data["error"] = "no connection"
                return JsonResponse(data, status=401)
        elif source == "FRA":
            private_bears = list()
            institutional_bears = list()
            try:
                fra = json.loads(sentiment_dao.lookupData("FRA", size))
                for entry in fra["institutionals"]:
                    institutional_bears.append({"time": entry["date"], "value": entry["bears"]})
                for entry in fra["privates"]:
                    private_bears.append({"time": entry["date"], "value": entry["bears"]})
                data["institutional_bears"] = institutional_bears
                data["private_bears"] = private_bears
            except:
                data["error"] = "no connection"
                return JsonResponse(data, status=401)
            
        elif source == "FRA_SPREAD":
            spread = list()
            p_basis = dict()
            i_basis = dict()
            try:
                fra = json.loads(sentiment_dao.lookupData("FRA", size))
                for entry in fra["institutionals"]:
                    i_basis[entry["date"]] = {"i_value": entry["bulls"] - entry["bears"]}
                for entry in fra["privates"]:
                    p_basis[entry["date"]] = {"p_value": entry["bulls"] - entry["bears"]}

                for entry in p_basis:
                    value = i_basis[entry]["i_value"] - p_basis[entry]["p_value"]
                    spread.append({"time": entry, "value": value})

                data["fra_spread"] = spread
            except:
                data["error"] = "no connection"
                return JsonResponse(data, status=401)

        return JsonResponse(data, status=201)
    return JsonResponse(data, status=404)


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


@login_required()
@user_passes_test(is_manager, login_url="start")
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
        logger.info(f"User {admin} created")

    try:
        data_provider = DataProvider.objects.get(name="Yahoo")
    except ObjectDoesNotExist:
        data_provider = DataProvider(
            name="Yahoo", description="Provider for finance.yahoo.com"
        )
        data_provider.save()
        logger.info(f"Data provider {data_provider} created")

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
            logger.info(f"created {watchlist}")

        # add securities to watchlist
        for symbol in list:
            price = online_dao.lookupPrice(symbol)

            # create new Security
            try:
                sec = Security.objects.get(symbol=symbol, data_provider=data_provider)
                watchlist.securities.add(sec)
                logger.info(f"added {sec} to {watchlist}")
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
            logger.info(f"added {sec} to {watchlist}")

    return JsonResponse({"status": "all done"}, status=201)


from data.sp500_helper import import_sp500


@login_required()
@user_passes_test(is_manager, login_url="start")
def create_sp500_list(request):
    import_sp500()
    return JsonResponse({"status": "all done"}, status=201)
