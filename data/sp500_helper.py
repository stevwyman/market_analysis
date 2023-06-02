import csv
import time
from data.models import User, Watchlist, Security, DataProvider, Daily, DailyUpdate
from data.history_dao import History_DAO_Factory
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, transaction

from logging import getLogger

logger = getLogger(__name__)

def import_sp500():

    # if not existing, create a default user
    try:
        admin = User.objects.get(username="myAdmin")
    except ObjectDoesNotExist:
        admin = User(username="myAdmin", email="admin@admin.de", password="_admin-123")
        admin.role = 1
        admin.save()
        logger.info(f"User {admin} created")

    # is not existing, create the data provider
    try:
        data_provider = DataProvider.objects.get(name="Tiingo")
    except ObjectDoesNotExist:
        data_provider = DataProvider(
            name="Tiingo", description="Provider for tiingo.com"
        )
        data_provider.save()
        logger.info(f"Created data provider: {data_provider}")

    # if not existing, create the watchlist
    try:
        watchlist = Watchlist.objects.get(name="S&P 500")
    except ObjectDoesNotExist:
        watchlist = Watchlist(name=name, user=admin, visibility="AP")
        watchlist.save()
        logger.info(f"Created watchlist: {watchlist}")

    history_dao = History_DAO_Factory().get_online_dao(data_provider)
    
    with open("SP500.csv", newline='') as csvfile:
        # read file with symbols
        reader = csv.reader(csvfile, delimiter=';', quotechar='|')
        # Symbol;Security;GICS Sector;GICS Sub-Industry;Headquarters Location;Date added;CIK;Founded
        for row in reader:
            # read data from file
            symbol = row[0]

            try:
                sec = Security.objects.get(symbol=symbol, data_provider=data_provider)
                logger.info(f"Entry with {symbol} already exists, hence skipping entry")
                continue
            except ObjectDoesNotExist:
                logger.info("Processing " + symbol)

            name = row[1]
            sector = row[2]
            industry = row[3]

            # create a price metadata object
            price_metadata = {}
            price_metadata["symbol"] = symbol
            price_metadata["shortName"] = name
            price_metadata["currencySymbol"] = "$"
            price_metadata["currency"] = "USD"
            price_metadata["quoteType"] = "EQUITY"
            price_metadata["exchangeName"] = "NYSE"

            # create a summary profile metadata object
            # probably no need to sore the data in the database
            summaryProfile_metadata = {}
            summaryProfile_metadata["symbol"] = symbol
            summaryProfile_metadata["sector"] = sector
            summaryProfile_metadata["industry"] = industry
            summaryProfile_metadata["country"] = "USA"

            sec = Security.objects.create(
                symbol=symbol, name=name, data_provider=data_provider
            )
            sec.currency_symbol = price_metadata["currencySymbol"]
            sec.currency = price_metadata["currency"]
            sec.type = price_metadata["quoteType"]
            sec.exchange = price_metadata["exchangeName"]

            # store in summary profile
            sec.country = summaryProfile_metadata["country"]
            sec.industry = summaryProfile_metadata["industry"]
            sec.sector = summaryProfile_metadata["sector"]

            # request new history from online dao
            try:
                result = history_dao.lookupHistory(security=sec, look_back=10000)
                if len(result) > 10:
                    try:

                        sec.save()
                        watchlist.securities.add(sec)
                        history_dao.storePriceMetadata(price_metadata)

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
                            logger.info("History has been updated for " + symbol)

                    except DatabaseError as db_error:
                        logger.warn(db_error)
            except ValueError as v_error:
                logger.error(v_error)

            # Polygon wait for 12 sec as the API only accepts 5 calls/minute
            # Tiingo 7 sec
            time.sleep(7)
    