from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from datetime import datetime, date
from data.technical_analysis import EMA, SMA, BollingerBands, MACD, RSI

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
)
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


def watchlist(request, watchlist_id: int):
    watchlist = Watchlist.objects.get(pk=watchlist_id)
    securities = watchlist.securities.order_by("name").all()

    # building watchlist
    watchlist_entries = list()
    for security in securities:
        watchlist_entry = {}
        watchlist_entry["security"] = security
        dao = History_DAO_Factory().get_online_dao(security.data_provider)
        watchlist_entry["price"] = humanize_price(dao.lookupPrice(security.symbol))

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
            "price": humanize_price(price),
            # for testing
            # "quote_summary": quoteSummary
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
            try:
                sec.country = summaryProfile["country"]
                sec.industry = summaryProfile["industry"]
                sec.sector = summaryProfile["sector"]
            except:
                if "error" in summaryProfile.keys():
                    messages.warning(request, summaryProfile["error"])
                else:
                    messages.warning(
                        request, "no valid data for 'country, 'industry', or 'sector' "
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


def security_search(request) -> JsonResponse:
    data = {}

    if request.method == "POST":
        query = request.POST["id"]

        results = list()
        securities = Security.objects.filter(
            Q(name__contains=query) | Q(symbol__contains=query)
        )
        print(f"found {securities.count()} entries for {query}")

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

    #data[f"EMA(50)[{sec.currency_symbol}]"] = ema50_value
    data["δEMA(50)[%]"] = 100 * (close - ema50_value) / ema50_value
    #data[f"EMA(20)[{sec.currency_symbol}]"] = ema20_value
    data["δEMA(20)[%]"] = 100 * (close - ema20_value) / ema20_value
    data["MACD <sub>Histogram</sub>"] = macd_value[2]
    data["RSI"] = rsi_value
    data["MA(50) spread"] = sma50.sigma_delta()

    bb_center = (bb_value[0] + bb_value[1])/2
    bb_position_rel = close - bb_center
    if bb_position_rel >= 0: # we are in the upper band
        data["BBands"] = 100 * bb_position_rel / (bb_value[1] - bb_center) 
    else:
        data["BBands"] = -100 * bb_position_rel / (bb_value[0] - bb_center) 

    hurst_value = sma50.hurst()
    if hurst_value > 0.5:
        data["Hurst<sub>trending</sub>"] = hurst_value
    else:
        data["Hurst<sub>mean rev.</sub>"] = hurst_value
    
    return JsonResponse(data, status=201)


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


def update_all(request):
    data = {}

    all_securities = Security.objects.all()
    counter = 0
    for security in all_securities:
        _today = date.today()
        last_updated = security.dailyupdate_data.all().first()

        if last_updated is not None:
            if last_updated.date == _today:
                print(f"no update required for {security}")
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
                    messages.info(request, "Daily history has been updated")

            except DatabaseError as db_error:
                print(db_error)

        time.sleep(5)

    return JsonResponse(data, status=200)


import pandas as pd


def build_data_set(request) -> JsonResponse:
    """
    building a data structure that can be used as input for an AI algorithm
    """
    data = list()

    all_securities = Security.objects.all()
    # all_securities = Security.objects.filter(symbol="ADS.DE")

    for security in all_securities:
        if security.type != "EQUITY":
            logger.debug(f"skipping {security} as not an equity")
            continue
        else:
            logger.info(f"processing {security}")

        history = list(security.daily_data.order_by("date").all())
        logger.debug(f"... history size: {len(history)}")

        # define the list of features
        sma50 = SMA(50)     # mid term sma: rel. slope, delta, hurst and sigma delta
        ema20 = EMA(20)     # short term ema: rel. slope, delta
        macd = MACD()       # not sure if we want to use the MACD, requires a lot of regularisation
        rsi = RSI()         # using a simple momentum indicator

        previous_close = 0
        previous_sma50 = 0
        previous_ema20 = 0
        previous_rsi = 0

        history_size = len(history)
        index = 0
        FORWARD_LABEL_SIZE = 5
        for entry in history:
            # the last are irrelevant, as we do not have any label information for those
            if (index + FORWARD_LABEL_SIZE + 1) > history_size:
                logger.debug("continue")
                continue

            row = {}

            # the close as input for all the indicators
            __close = float(entry.close)
            # logger.debug(f"processing {entry.date} with close at {__close}")
            

            if previous_close != 0:
                # keep those three as reference
                row["time"] = str(entry.date)
                row["close"] = __close
                row["symbol"] = security.symbol

                # this will be our label
                next_close = float(history[index + FORWARD_LABEL_SIZE].close)

                # we need to ensure that extreme values are capped, so they do not corrupt our min/max  afterwards
                # -> so we cap all at 10%

                __change_back_percent = (
                    100 * (__close - previous_close) / previous_close
                )
                if __change_back_percent > 10:
                    __change_back_percent = 10
            
                # just for reference
                row["change_back"] = __change_back_percent

                # building the label, using the forward percent as category 
                __change_forward_percent = 100 * (next_close - __close) / __close

                if __change_forward_percent > 10:
                    __change_forward_percent = 10
                elif __change_forward_percent < -10:
                    __change_forward_percent = -10

                if __change_forward_percent < 0:
                    __change_forward_percent += 20

                row["change_forward"] = round(__change_forward_percent, 0)
                
                previous_close = __close
                index += 1
            else:
                previous_close = __close
                index += 1
                continue

            # now we work on the features
            # macd
            macd_value = macd.add(__close)
            if macd_value is not None:
                row["macd_histogram"] = macd_value[2]


            # ema20
            ema20_value = ema20.add(__close)
            if previous_ema20 != 0:
                if ema20_value is not None and previous_ema20 is not None:
                    # just as a reference
                    row["ema20"] = ema20_value
                    # we will use those as features
                    row["ema20_delta"] = (__close - ema20_value) / ema20_value
                    row["ema20_slope"] = (ema20_value - previous_ema20) / previous_ema20

            previous_ema20 = ema20_value

            # sma50
            sma50_value = sma50.add(__close)
            if previous_sma50 != 0:
                if sma50_value is not None and previous_sma50 is not None:
                    sma50_sd = sma50.sigma_delta()
                    sma50_hurst = sma50.hurst()
                    if (
                        sma50_value is not None
                        and sma50_sd is not None
                        and sma50_hurst is not None
                    ):
                        # reference
                        row["sma50"] = sma50_value
                        # features
                        row["sd50"] = sma50_sd
                        row["hurst"] = sma50_hurst
                        row["sma50_delta"] = (__close - sma50_value) / sma50_value
                        row["sma50_slope"] = (sma50_value - previous_sma50) / previous_sma50

            previous_sma50 = sma50_value

            # rsi
            rsi_value = rsi.add(__close)
            if previous_rsi != 0:
                if rsi_value is not None and previous_rsi is not None:
                    row["rsi"] = rsi_value
                    row["rsi_slope"] = (rsi_value - previous_rsi) / previous_rsi
            previous_rsi = rsi_value

            # only append complete rows
            if len(row) == 16:
                logger.debug(f"... appending {row}")
                data.append(row)

    df = pd.DataFrame(data)
    compression_opts = dict(method="zip", archive_name="out.csv")
    df.to_csv("out.zip", index=False, compression=compression_opts)

    response_data = {}
    response_data["lines"] = len(data)
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

    distribution = generate_most_distribution(parameter)

    return JsonResponse(distribution, status=200)


#
# init the default watchlists
#
from data.indices import DATA


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
        watchlist = Watchlist(name=name, user=admin, visibility="AP")
        watchlist.save()
        print(f"created {watchlist}")

        # add securities to watchlist
        for symbol in list:
            price = online_dao.lookupPrice(symbol)

            # create new Security
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

    return JsonResponse({"all done", 201})
