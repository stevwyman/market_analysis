import json
import csv
import urllib3
from io import StringIO
import decimal

import pymongo
import threading

lock = threading.Lock()

from django.conf import settings

from enum import Enum
from time import time
from datetime import date, datetime, timedelta
from os import environ
from logging import getLogger

logger = getLogger(__name__)

from data.models import Daily, Security
from data.meta_dao import MetaData_Factory


class Interval(Enum):
    HOURLY = "1h"
    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"


def synchronized(lock):
    """ Synchronization decorator """
    def wrap(f):
        def newFunction(*args, **kw):
            with lock:
                return f(*args, **kw)
        return newFunction
    return wrap


class SingletonOptmized(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._locked_call(*args, **kwargs)
        return cls._instances[cls]

    @synchronized(lock)
    def _locked_call(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonOptmized, cls).__call__(*args, **kwargs)


class History_DAO_Factory():

    def get_online_dao(self, data_provider):
        if data_provider.name == "Yahoo":
            return YahooDAO()
        elif data_provider.name == "Polygon":
            return PolygonDAO()
        elif data_provider.name == "Tiingo":
            return TiingoDAO()
        elif data_provider.name == "Onvista":
            return OnvistaDAO()
        elif data_provider.name == "wyca-analytics":
            return ComWycaDAO()
        elif data_provider.name == "WSJ":
            return MarketDiaryDAO()
        else:
            raise ValueError(format)
        

class YahooDAO():
    _instance = None
    _lock = threading.Lock()
    _mongo_db = None
    _history_client = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # Another thread could have created the instance
                # before we acquired the lock. So check that the
                # instance is still nonexistent.
                if cls._instance is None:
                    # cls._instance = super().__new__(cls)
                    logger.debug("Creating YahooDAO")
                    cls._instance = super(YahooDAO, cls).__new__(cls)
                    # initialisation
                    # cls._http_client = urllib3.HTTPConnectionPool("yahoo.com", maxsize=10)
                    cls._history_client = urllib3.PoolManager()
                    # cls._mongo_db = MetaData_Factory().db("market_analysis")
                    # we have to ensure, that each process receives its own client 
                    cls._mongo_db = MetaData_Factory().client().db["market_analysis"]
        return cls._instance

    def lookupSymbol(self, symbol) -> dict:
        """
        returns, if found, the "summaryProfile" data set

        {"quoteSummary":
            {"result":[
                {"summaryProfile":
                    {"address1":"One Apple Park Way","city":"Cupertino","state":"CA","zip":"95014","country":"United States","phone":"408 996 1010","website":"https://www.apple.com",
                    "industry":"Consumer Electronics","sector":"Technology","longBusinessSummary":"Apple Inc. designs, ...","fullTimeEmployees":164000,"companyOfficers":[],"maxAge":86400}}],"error":null}}

        """

        http = self._history_client
        r = http.request(
            "GET",
            "https://query2.finance.yahoo.com/v10/finance/quoteSummary/" + symbol,
            fields={
                "formatted": "true",
                "lang": "en-US",
                "region": "US",
                "modules": "summaryProfile",
                "corsDomain": "finance.yahoo.com",
            },
        )

        summary_profile = json.loads(r.data.decode("utf-8"))

        logger.debug(
            "status for requesting 'summary profile' of %s: %s " % (symbol, r.status)
        )

        if r.status == 200:
            return summary_profile["quoteSummary"]["result"][0]["summaryProfile"]
        else:
            error = summary_profile["quoteSummary"]["error"]
            return {"error": error["description"]}

    def lookupPrice(self, symbol) -> dict:
        """
        returns, if found, the "price" data set

        {"quoteSummary":
            {"result":[
                {"price":
                    {"maxAge":1,
                    "preMarketChangePercent":{"raw":-0.00954487,"fmt":"-0.95%"},
                    "preMarketChange":{"raw":-1.60001,"fmt":"-1.60"},
                    "preMarketTime":1681997399,
                    "preMarketPrice":{"raw":166.03,"fmt":"166.03"},
                    "preMarketSource":"FREE_REALTIME",
                    "postMarketChange":{},
                    "postMarketPrice":{},
                    "regularMarketChangePercent":{"raw":-0.0011931766,"fmt":"-0.12%"},
                    "regularMarketChange":{"raw":-0.2000122,"fmt":"-0.20"},
                    "regularMarketTime":1682013624,
                    "priceHint":{"raw":2,"fmt":"2","longFmt":"2"},
                    "regularMarketPrice":{"raw":167.43,"fmt":"167.43"},
                    "regularMarketDayHigh":{"raw":167.87,"fmt":"167.87"},
                    "regularMarketDayLow":{"raw":165.91,"fmt":"165.91"},"regularMarketVolume":{"raw":28145554,"fmt":"28.15M","longFmt":"28,145,554.00"},"averageDailyVolume10Day":{},"averageDailyVolume3Month":{},"regularMarketPreviousClose":{"raw":167.63,"fmt":"167.63"},"regularMarketSource":"FREE_REALTIME","regularMarketOpen":{"raw":166.09,"fmt":"166.09"},"strikePrice":{},"openInterest":{},"exchange":"NMS","exchangeName":"NasdaqGS","exchangeDataDelayedBy":0,"marketState":"REGULAR","quoteType":"EQUITY","symbol":"AAPL","underlyingSymbol":null,
                    "shortName":"Apple Inc.","longName":"Apple Inc.","currency":"USD","quoteSourceName":"Nasdaq Real Time Price",
                    "currencySymbol":"$","fromCurrency":null,"toCurrency":null,"lastMarket":null,"volume24Hr":{},"volumeAllCurrencies":{},"circulatingSupply":{},"marketCap":{"raw":2649060540416,"fmt":"2.65T","longFmt":"2,649,060,540,416.00"}}}],"error":null}}
        """
        _price = self._mongo_db["yahoo_price"]

        try:
            # check if we have a price entry in the mongo-db
            db_price = _price.find_one({"symbol": symbol})
            if db_price is None:
                logger.debug("no 'price' for %s" % symbol)
            else:
                # check if the available entry is older than 5 minutes
                entry_ts = db_price["timestamp"]
                current_ts = datetime.now().timestamp()

                if entry_ts + 300 > current_ts:   # for production 5 minutes
                #if entry_ts + 3600 > current_ts:  # for testing 1 hour
                    # print(f"serving price for {symbol} from db")
                    logger.debug("serving price for %s from db" % symbol)
                    return db_price["price"]
                else:
                    logger.debug("update of price required for %s" % symbol)

        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error("Could not read data from locale storage: ", e)

        http = self._history_client
        r = http.request(
            "GET",
            "https://query2.finance.yahoo.com/v10/finance/quoteSummary/" + symbol,
            fields={
                "formatted": "true",
                "lang": "en-US",
                "region": "US",
                "modules": "price",
                "corsDomain": "finance.yahoo.com",
            },
        )
        logger.debug("status for requesting 'price' of %s: %s " % (symbol, r.status))
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            price = summary_profile["quoteSummary"]["result"][0]["price"]

            _data = {"timestamp": datetime.now().timestamp(), "price": price}
            _price.update_one({"symbol": symbol}, {"$set": _data}, upsert=True)
            return price
        else:
            logger.error("status for requesting 'price' of %s: %s " % (symbol, r.status))
            if "finance" in summary_profile:
                error_description = summary_profile["finance"]["error"]["description"]
            elif "quoteSummary" in summary_profile:
                error_description = summary_profile["quoteSummary"]["error"]["description"]
            else:
                logger.error(summary_profile)
                error_description = f"could not get quoteSummary for {symbol}"
            
            logger.error(f"with error: {error_description}")
            if db_price is not None:
                return db_price["price"]
            else:
                return {"error": error_description}

            

    def lookupHistory(self, security: Security, interval=Interval.DAILY, look_back=200):
        """
        returns, if found, the "historic" data set
        """

        to_time = int(round(time()))
        start_time: datetime = datetime.today() - timedelta(days=look_back)
        from_time = int(round(start_time.timestamp()))

        # print(f"requesting from: {from_time} to: {to_time} with interval: {interval.value}")

        http = self._history_client
        r = http.request(
            "GET",
            "https://query1.finance.yahoo.com/v7/finance/download/" + security.symbol,
            fields={
                "period1": from_time,  # the date to start from in milliseconds
                "period2": to_time,  # to date in milliseconds
                "interval": interval.value,
                "events": "history",
            },
        )

        logger.debug(
            "status for requesting 'history' of %s: %s " % (security.symbol, r.status)
        )

        data = r.data.decode("utf-8")

        # print(data)

        reader = csv.DictReader(StringIO(data), delimiter=",")
        historic_entries = list()
        today = date.today()
        for row in reader:
            # print(row)
            date_str = row["Date"]
            # don't add today's value from history, use the price instead
            if date_str == str(today):
                continue
            open_str = row["Open"]
            # some entries only have a date, but not a value i.e. bank holiday
            if open_str == "null":
                continue
            high_str = row["High"]
            low_str = row["Low"]
            close_adj_str = row["Adj Close"]
            close_str = row["Close"]
            volume_str = row["Volume"]

            entry = Daily(
                date=datetime.strptime(date_str, "%Y-%m-%d").date(),
                security=security,
                open_price=decimal.Decimal(open_str),
                high_price=decimal.Decimal(high_str),
                low=decimal.Decimal(low_str),
                close=decimal.Decimal(close_str),
                adj_close=decimal.Decimal(close_adj_str),
                volume=int(volume_str),
            )

            historic_entries.append(entry)

        return historic_entries

    def lookup_default_key_statistics(self, security: Security) -> dict:
        """
        returns, if found, the "defaultKeyStatistics" data set
        """
        if security.type != "EQUITY":
            return {"error": "Not an equity."}
        else:
            symbol = security.symbol

        _defaultKeyStatistics = self._mongo_db["defaultKeyStatistics"]
        try:
            # check if we have a price entry in the mongo-db
            defaultKeyStatistics = _defaultKeyStatistics.find_one({"symbol": symbol})
            if defaultKeyStatistics is None:
                logger.debug("no 'default key statistics' for %s" % symbol)
            else:
                # check if the available entry is older than 5 minutes
                entry_ts = defaultKeyStatistics["timestamp"]
                current_ts = datetime.now().timestamp()

                if entry_ts + 86400 > current_ts:  # for testing 1 day
                    print(f"serving 'defaultKeyStatistics' for {symbol} from db")
                    return defaultKeyStatistics["defaultKeyStatistics"]
                else:
                    print(f"need to refresh the 'defaultKeyStatistics' in the database")

        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not write data to locale storage: ", e)

        http = self._history_client
        r = http.request(
            "GET",
            "https://query2.finance.yahoo.com/v10/finance/quoteSummary/" + symbol,
            fields={
                "formatted": "true",
                "lang": "en-US",
                "region": "US",
                "modules": "defaultKeyStatistics",
                "corsDomain": "finance.yahoo.com",
            },
        )
        logger.debug(
            "status for requesting 'default key statistics' of %s: %s "
            % (symbol, r.status)
        )
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            defaultKeyStatistics = summary_profile["quoteSummary"]["result"][0][
                "defaultKeyStatistics"
            ]

            _data = {
                "timestamp": datetime.now().timestamp(),
                "defaultKeyStatistics": defaultKeyStatistics,
            }
            _defaultKeyStatistics.update_one(
                {"symbol": symbol}, {"$set": _data}, upsert=True
            )
            return defaultKeyStatistics
        else:
            error = summary_profile["quoteSummary"]["error"]
            return {"error": error["description"]}

    # assetProfile
    def lookupAssetProfile(self, security: Security) -> dict:
        """
        returns, if found, the "assetProfile" data set
        """
        if security.type != "EQUITY":
            return {"error": "Not an equity."}
        else:
            symbol = security.symbol
        _collection_assetProfile = self._mongo_db["assetProfile"]
        try:
            # check if we have a price entry in the mongo-db
            assetProfile = _collection_assetProfile.find_one({"symbol": symbol})
            if assetProfile is None:
                print(f"no price object for {symbol}")
            else:
                # check if the available entry is older than 5 minutes
                entry_ts = assetProfile["timestamp"]
                current_ts = datetime.now().timestamp()

                if entry_ts + 86400 > current_ts:  # for testing 1 day
                    print(f"serving 'assetProfile' for {symbol} from db")
                    return assetProfile["assetProfile"]
                else:
                    print(f"need to refresh the 'assetProfile' in the database")

        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not write data to locale storage: ", e)

        http = self._history_client
        r = http.request(
            "GET",
            "https://query2.finance.yahoo.com/v10/finance/quoteSummary/" + symbol,
            fields={
                "formatted": "true",
                "lang": "en-US",
                "region": "US",
                "modules": "assetProfile",
                "corsDomain": "finance.yahoo.com",
            },
        )
        logger.debug(
            "status for requesting 'asset profile' of %s: %s " % (symbol, r.status)
        )
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            assetProfile = summary_profile["quoteSummary"]["result"][0]["assetProfile"]

            _data = {
                "timestamp": datetime.now().timestamp(),
                "assetProfile": assetProfile,
            }
            _collection_assetProfile.update_one(
                {"symbol": symbol}, {"$set": _data}, upsert=True
            )
            return assetProfile
        else:
            error = summary_profile["quoteSummary"]["error"]
            return {"error": error["description"]}

    # financialData
    def lookup_financial_data(self, security: Security) -> dict:
        """
        returns, if found, the "financialData" data set
        """
        if security.type != "EQUITY":
            return {"error": "Not an equity."}
        else:
            symbol = security.symbol
        _collection_financialData = self._mongo_db["financialData"]
        try:
            # check if we have a price entry in the mongo-db
            financialData = _collection_financialData.find_one({"symbol": symbol})
            if financialData is None:
                print(f"no price object for {symbol}")
            else:
                # check if the available entry is older than 5 minutes
                entry_ts = financialData["timestamp"]
                current_ts = datetime.now().timestamp()

                if entry_ts + 86400 > current_ts:  # for testing 1 day
                    print(f"serving 'financialData' for {symbol} from db")
                    return financialData["financialData"]
                else:
                    print(f"need to refresh the 'financialData' in the database")

        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not write data to locale storage: ", e)

        http = self._history_client
        r = http.request(
            "GET",
            "https://query2.finance.yahoo.com/v10/finance/quoteSummary/" + symbol,
            fields={
                "formatted": "true",
                "lang": "en-US",
                "region": "US",
                "modules": "financialData",
                "corsDomain": "finance.yahoo.com",
            },
        )
        logger.debug(
            "status for requesting 'finacial data' of %s: %s " % (symbol, r.status)
        )
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            financialData = summary_profile["quoteSummary"]["result"][0][
                "financialData"
            ]

            _data = {
                "timestamp": datetime.now().timestamp(),
                "financialData": financialData,
            }
            _collection_financialData.update_one(
                {"symbol": symbol}, {"$set": _data}, upsert=True
            )
            return financialData
        else:
            error = summary_profile["quoteSummary"]["error"]
            return {"error": error["description"]}

    # summary_detail
    def lookup_summary_detail(self, security: Security) -> dict:
        """
        returns, if found, the "summaryDetail" data set
        """
        if security.type != "EQUITY":
            return {"error": "Not an equity."}
        else:
            symbol = security.symbol

        _collection_summaryDetail = self._mongo_db["summaryDetail"]
        try:
            # check if we have a price entry in the mongo-db
            summaryDetail = _collection_summaryDetail.find_one({"symbol": symbol})
            if summaryDetail is None:
                logger.debug("no 'summary detail' for %s" % symbol)
            else:
                # check if the available entry is older than 5 minutes
                entry_ts = summaryDetail["timestamp"]
                current_ts = datetime.now().timestamp()

                if entry_ts + 86400 > current_ts:  # for testing 1 day
                    logger.debug("serving 'summary detail' for %s from db " % symbol)
                    return summaryDetail["summaryDetail"]
                else:
                    logger.debug("need to refresh 'summary detail' for %s" % symbol)

        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error("Could not write data to local storage: %s" % e)

        http = self._history_client
        r = http.request(
            "GET",
            "https://query2.finance.yahoo.com/v10/finance/quoteSummary/" + symbol,
            fields={
                "formatted": "true",
                "lang": "en-US",
                "region": "US",
                "modules": "summaryDetail",
                "corsDomain": "finance.yahoo.com",
            },
        )
        logger.debug(
            "status for requesting 'summary detail' of %s: %s " % (symbol, r.status)
        )

        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            summaryDetail = summary_profile["quoteSummary"]["result"][0][
                "summaryDetail"
            ]

            _data = {
                "timestamp": datetime.now().timestamp(),
                "summaryDetail": summaryDetail,
            }
            _collection_summaryDetail.update_one(
                {"symbol": symbol}, {"$set": _data}, upsert=True
            )
            return summaryDetail
        else:
            error = summary_profile["quoteSummary"]["error"]
            return {"error": error["description"]}


class PolygonDAO:
    _instance = None
    _mongo_db = None
    _api_key = "###"
    _http_client = urllib3.PoolManager()

    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating PolygonDAO")
            cls._instance = super(PolygonDAO, cls).__new__(cls)
            # initialisation
            cls._api_key = environ.get("POLYGON_API_KEY")
            cls._mongo_db = MetaData_Factory().db("market_analysis")

        return cls._instance

    def lookupHistory(self, security: Security, interval=Interval.DAILY, look_back=200):
        # Contact API

        # data used to complie the query to get the history -> 2year in this case
        now = datetime.now()
        fromDate = (now - timedelta(look_back)).strftime("%Y-%m-%d")
        endDate = now.strftime("%Y-%m-%d")

        logger.debug(
            f"requesting history for {security} using from:{fromDate} to:{endDate}"
        )

        if interval == Interval.DAILY:
            range = "/range/1/day/"
        else:
            range = "nope"

        http = self._http_client
        try:
            r = http.request(
                "GET",
                "https://api.polygon.io/v2/aggs/ticker/"
                + security.symbol
                + range
                + fromDate
                + "/"
                + endDate,
                fields={
                    "adjusted": "true",  # the date to start from in milliseconds
                    "sort": "asc",  # to date in milliseconds
                    "apiKey": self._api_key,
                },
            )
        except urllib3.error.HTTPError as error:
            logger.error("HTTP Error: Data not retrieved because %s", error)
        except urllib3.error.URLError as error:
            logger.error("URL Error: Data not retrieved because %s", error)

        status_code = r.status
        logger.debug(
            "status for requesting 'history' of %s: %s "
            % (security.symbol, status_code)
        )

        if status_code != 200:
            logger.error(f"Could not get receive data, status code: {status_code}")
            raise ValueError("No data available")

        data = json.loads(r.data.decode("utf-8"))
        # logger.debug(data)

        # Parse response
        historic_entries = list()
        today = date.today()
        for row in data["results"]:
            # logger.debug(row)
            # date is in timestamp format: 1672117200000
            date_obj = datetime.fromtimestamp(row["t"] / 1000)
            date_str = datetime.strftime(date_obj, "%Y-%m-%d")
            # don't add today's value from history, use the price instead
            if date_str == str(today):
                continue
            open_str = row["o"]
            # some entries only have a date, but not a value i.e. bank holiday
            if open_str == "null":
                continue

            entry = Daily(
                date=datetime.strptime(date_str, "%Y-%m-%d").date(),
                security=security,
                open_price=row["o"],
                high_price=row["h"],
                low=row["l"],
                close=row["c"],
                adj_close=row["c"],
                volume=row["v"],
            )

            historic_entries.append(entry)

        return historic_entries

    def lookupPrice(self, symbol):
        """
        returns, if found, the "price" data set

        {"quoteSummary":
            {"result":[
                {"price":
                    {"maxAge":1,
                    "preMarketChangePercent":{"raw":-0.00954487,"fmt":"-0.95%"},
                    "preMarketChange":{"raw":-1.60001,"fmt":"-1.60"},
                    "preMarketTime":1681997399,
                    "preMarketPrice":{"raw":166.03,"fmt":"166.03"},
                    "preMarketSource":"FREE_REALTIME",
                    "postMarketChange":{},
                    "postMarketPrice":{},
                    "regularMarketChangePercent":{"raw":-0.0011931766,"fmt":"-0.12%"},
                    "regularMarketChange":{"raw":-0.2000122,"fmt":"-0.20"},
                    "regularMarketTime":1682013624,
                    "priceHint":{"raw":2,"fmt":"2","longFmt":"2"},
                    "regularMarketPrice":{"raw":167.43,"fmt":"167.43"},
                    "regularMarketDayHigh":{"raw":167.87,"fmt":"167.87"},
                    "regularMarketDayLow":{"raw":165.91,"fmt":"165.91"},"regularMarketVolume":{"raw":28145554,"fmt":"28.15M","longFmt":"28,145,554.00"},"averageDailyVolume10Day":{},"averageDailyVolume3Month":{},"regularMarketPreviousClose":{"raw":167.63,"fmt":"167.63"},"regularMarketSource":"FREE_REALTIME","regularMarketOpen":{"raw":166.09,"fmt":"166.09"},"strikePrice":{},"openInterest":{},"exchange":"NMS","exchangeName":"NasdaqGS","exchangeDataDelayedBy":0,"marketState":"REGULAR","quoteType":"EQUITY","symbol":"AAPL","underlyingSymbol":null,
                    "shortName":"Apple Inc.","longName":"Apple Inc.","currency":"USD","quoteSourceName":"Nasdaq Real Time Price",
                    "currencySymbol":"$","fromCurrency":null,"toCurrency":null,"lastMarket":null,"volume24Hr":{},"volumeAllCurrencies":{},"circulatingSupply":{},"marketCap":{"raw":2649060540416,"fmt":"2.65T","longFmt":"2,649,060,540,416.00"}}}],"error":null}}
        """

        _price = self._mongo_db["polygon_price"]
        try:
            # check if we have a price entry in the mongo-db
            price = _price.find_one({"symbol": symbol})
            return price["price"]
        except:
            logger.warn("No data found for " + symbol)
            return None

    def storePriceMetadata(self, metadata):
        _price = self._mongo_db["polygon_price"]
        try:
            _data = {"timestamp": datetime.now().timestamp(), "price": metadata}
            _price.update_one(
                {"symbol": metadata["symbol"]}, {"$set": _data}, upsert=True
            )
        except:
            logger.info("Could not store data")

    def lookupSymbol(self, symbol):
        return None


class TiingoDAO:
    _instance = None
    _lock = threading.Lock()
    _mongo_db = None
    _history_client = None
    _api_key = "###"

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # Another thread could have created the instance
                # before we acquired the lock. So check that the
                # instance is still nonexistent.
                if cls._instance is None:
                    # cls._instance = super().__new__(cls)
                    logger.debug("Creating Tiingo Singletonn")
                    cls._instance = super(TiingoDAO, cls).__new__(cls)
                    # initialisation
                    cls._api_key = environ.get("TIINGO_API_KEY")
                    cls._history_client = urllib3.PoolManager()
                    # we have to ensure, that each process receives its own client 
                    cls._mongo_db = MetaData_Factory().client().db["market_analysis"]
        return cls._instance

    def lookupHistory(self, security: Security, interval=Interval.DAILY, look_back=200):
        """
        returns, if found, the "historic" data set
        """

        # data used to complie the query to get the history -> 2year in this case
        now = datetime.now()
        fromDate = (now - timedelta(look_back)).strftime("%Y-%m-%d")
        endDate = now.strftime("%Y-%m-%d")

        logger.debug(
            f"requesting {security.symbol} from: {fromDate} to: {endDate} with interval: {interval.value}"
        )

        http = self._history_client
        r = http.request(
            "GET",
            "https://api.tiingo.com/tiingo/daily/" + security.symbol + "/prices",
            fields={
                "startDate": fromDate,  # the date to start from in milliseconds
                "endDate": endDate,  # to date in milliseconds
                "format": "csv",
                "resampleFreq": "daily",
                "token": self._api_key,
            },
        )

        logger.debug(
            "status for requesting 'history' of %s: %s " % (security.symbol, r.status)
        )

        data = r.data.decode("utf-8")

        logger.debug(data)

        reader = csv.DictReader(StringIO(data), delimiter=",")
        historic_entries = list()
        today = date.today()
        for row in reader:
            # print(row)
            date_str = row["date"]
            # don't add today's value from history, use the price instead
            if date_str == str(today):
                continue
            open_str = row["adjOpen"]
            # some entries only have a date, but not a value i.e. bank holiday
            if open_str == "null":
                continue
            high_str = row["adjHigh"]
            low_str = row["adjLow"]
            close_adj_str = row["adjClose"]
            close_str = row["adjClose"]
            volume_str = row["adjVolume"]

            entry = Daily(
                date=datetime.strptime(date_str, "%Y-%m-%d").date(),
                security=security,
                open_price=decimal.Decimal(open_str),
                high_price=decimal.Decimal(high_str),
                low=decimal.Decimal(low_str),
                close=decimal.Decimal(close_str),
                adj_close=decimal.Decimal(close_adj_str),
                volume=int(volume_str),
            )

            historic_entries.append(entry)

        return historic_entries

    def lookupPrice(self, symbol):
        """
        returns, if found, the "price" data set

        {"quoteSummary":
            {"result":[
                {"price":
                    {"maxAge":1,
                    "preMarketChangePercent":{"raw":-0.00954487,"fmt":"-0.95%"},
                    "preMarketChange":{"raw":-1.60001,"fmt":"-1.60"},
                    "preMarketTime":1681997399,
                    "preMarketPrice":{"raw":166.03,"fmt":"166.03"},
                    "preMarketSource":"FREE_REALTIME",
                    "postMarketChange":{},
                    "postMarketPrice":{},
                    "regularMarketChangePercent":{"raw":-0.0011931766,"fmt":"-0.12%"},
                    "regularMarketChange":{"raw":-0.2000122,"fmt":"-0.20"},
                    "regularMarketTime":1682013624,
                    "priceHint":{"raw":2,"fmt":"2","longFmt":"2"},
                    "regularMarketPrice":{"raw":167.43,"fmt":"167.43"},
                    "regularMarketDayHigh":{"raw":167.87,"fmt":"167.87"},
                    "regularMarketDayLow":{"raw":165.91,"fmt":"165.91"},"regularMarketVolume":{"raw":28145554,"fmt":"28.15M","longFmt":"28,145,554.00"},"averageDailyVolume10Day":{},"averageDailyVolume3Month":{},"regularMarketPreviousClose":{"raw":167.63,"fmt":"167.63"},"regularMarketSource":"FREE_REALTIME","regularMarketOpen":{"raw":166.09,"fmt":"166.09"},"strikePrice":{},"openInterest":{},"exchange":"NMS","exchangeName":"NasdaqGS","exchangeDataDelayedBy":0,"marketState":"REGULAR","quoteType":"EQUITY","symbol":"AAPL","underlyingSymbol":null,
                    "shortName":"Apple Inc.","longName":"Apple Inc.","currency":"USD","quoteSourceName":"Nasdaq Real Time Price",
                    "currencySymbol":"$","fromCurrency":null,"toCurrency":null,"lastMarket":null,"volume24Hr":{},"volumeAllCurrencies":{},"circulatingSupply":{},"marketCap":{"raw":2649060540416,"fmt":"2.65T","longFmt":"2,649,060,540,416.00"}}}],"error":null}}
        """

        _price = self._mongo_db["polygon_price"]
        try:
            # check if we have a price entry in the mongo-db
            price = _price.find_one({"symbol": symbol})
            return price["price"]
        except:
            logger.warn("No data found for " + symbol)
            return None

    def storePriceMetadata(self, metadata):
        _price = self._mongo_db["polygon_price"]
        try:
            _data = {"timestamp": datetime.now().timestamp(), "price": metadata}
            _price.update_one(
                {"symbol": metadata["symbol"]}, {"$set": _data}, upsert=True
            )
        except:
            logger.info("Could not store data")

    def lookupSymbol(self, symbol):
        return None


class OnvistaDAO:
    _instance = None
    _history_client = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating OnvistaDAO")
            cls._instance = super(OnvistaDAO, cls).__new__(cls)
            # initialisation
            #cls._history_client = urllib3.HTTPConnectionPool("api.onvista.de", maxsize=10)
            cls._history_client = urllib3.PoolManager(maxsize=10)
        return cls._instance

    def lookupIntraday(self, notation_id) -> dict:
        """
        returns, if found, the "intraday" data set
        """

        http = self._history_client
        r = http.request(
            "GET",
            f"https://api.onvista.de/api/v1/instruments/INDEX/{notation_id}/times_and_sales",
            fields={
                "idNotation": notation_id,
                "order": "DESC"
            },
            headers={"Content-Type":"application/json"}
        )

        result = json.loads(r.data.decode("utf-8"))

        logger.debug(
            "status for requesting 'lookup intraday' of %s: %s " % (notation_id, r.status)
        )

        return result


class ComWycaDAO:
    _instance = None
    _api_key = "test"
    _http_client = urllib3.PoolManager()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ComWycaDAO, cls).__new__(cls)
            # initialisation
            cls._api_key = environ.get("COMWYCA_API_KEY")
            logger.info(f"Created Comwyca")
        return cls._instance

    def lookupData(self, source:str, size:int) -> dict:
        """
        returns, the sentiment data
        """
        try:

            http = self._http_client
            r = http.request(
                "GET",
                f"https://wyca-analytics.com/data/sentiment",
                fields={
                    "apiKey": self._api_key,
                    "source": source,
                    "size": size
                },
                headers={"Content-Type":"application/json"}
            )
        except :
            logger.warn("Could not connect to wyca-analytics: ")
            return dict()
        
        if r.status != 200:
            logger.warn("Error getting data from wyca-analytics")
            return dict()
    

        return json.loads(r.data.decode("utf-8"))
        

class MarketDiaryDAO:       
    _instance = None
    _mongo_db = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating MarketDiaryDAO")
            cls._instance = super(MarketDiaryDAO, cls).__new__(cls)
            # initialisation
            cls._mongo_db = MetaData_Factory().db("local")

        return cls._instance

    def lookupHistory(self, look_back=250) -> list:
        """
        returns, if found, the "historic" data set
        """

        _market_diary = self._mongo_db["market_diary"]
        try:
            cursor = _market_diary.find().sort([("timestamp", -1)]).limit(look_back)
                    
        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error("Could not write data to local storage: %s" % e)

        return list(cursor)
