import json
import csv
import urllib3
from io import StringIO
import decimal

import pymongo
import configparser

from django.conf import settings

from enum import Enum
from time import time
from datetime import date, datetime, timedelta

from data.models import Daily, Security


class Interval(Enum):
    HOURLY = "1h"
    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"


class Online_DAO_Factory:
    def get_online_dao(self, data_provider):
        if data_provider.name == "Yahoo":
            return YahooDAO()
        else:
            raise ValueError(format)


class YahooDAO:
    def __init__(self) -> None:
        config = configparser.ConfigParser()
        config.read("config.ini")
        self._client = pymongo.MongoClient(config.get("DB", "url"))
        try:
            self._client.server_info()
        except pymongo.errors.ServerSelectionTimeoutError:
            exit("Mongo instance not reachable.")

        self._db = self._client[config.get("DB", "db")]
        self._collection_price = self._db[config.get("DB.YAHOO.PRICE", "collection")]
        self._collection_dks = self._db[config.get("DB.YAHOO.DKS", "collection")]

    def lookupSymbol(self, symbol) -> dict:
        """
        returns, if found, the "summaryProfile" data set

        {"quoteSummary":
            {"result":[
                {"summaryProfile":
                    {"address1":"One Apple Park Way","city":"Cupertino","state":"CA","zip":"95014","country":"United States","phone":"408 996 1010","website":"https://www.apple.com",
                    "industry":"Consumer Electronics","sector":"Technology","longBusinessSummary":"Apple Inc. designs, ...","fullTimeEmployees":164000,"companyOfficers":[],"maxAge":86400}}],"error":null}}

        """

        http = urllib3.PoolManager()
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

        print(f"status for requesting 'summary detail' of {symbol}: {r.status}")

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

        try:
            # check if we have a price entry in the mongo-db
            price = self._collection_price.find_one({"symbol": symbol})
            if price is None:
                print(f"no price object for {symbol}")
            else:
                # check if the available entry is older than 5 minutes
                entry_ts = price["timestamp"]
                current_ts = datetime.now().timestamp()

                # if entry_ts + 300 > current_ts:   # for production 5 minutes
                if entry_ts + 3600 > current_ts:  # for testing 1 hour
                    # print(f"serving price for {symbol} from db")
                    return price["price"]
                else:
                    print(f"need to refresh the price in the database")

        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not write data to locale storage: ", e)

        http = urllib3.PoolManager()
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
        print(f"status for requesting 'price' of {symbol}: {r.status}")
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            price = summary_profile["quoteSummary"]["result"][0]["price"]

            upsertable_data = {"timestamp": datetime.now().timestamp(), "price": price}
            self._collection_price.update_one(
                {"symbol": symbol}, {"$set": upsertable_data}, upsert=True
            )
            return price
        else:
            error = summary_profile["quoteSummary"]["error"]
            return {"error": error["description"]}

    def lookupHistory(self, security: Security, interval=Interval.DAILY, look_back=200):
        """
        returns, if found, the "historic" data set
        """

        to_time = int(round(time()))
        start_time: datetime = datetime.today() - timedelta(days=look_back)
        from_time = int(round(start_time.timestamp()))

        # print(f"requesting from: {from_time} to: {to_time} with interval: {interval.value}")

        http = urllib3.PoolManager()
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

        print(f"status for requesting 'history' of {security.symbol}: {r.status}")

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
        try:
            # check if we have a price entry in the mongo-db
            defaultKeyStatistics = self._collection_dks.find_one({"symbol": symbol})
            if defaultKeyStatistics is None:
                print(f"no price object for {symbol}")
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

        http = urllib3.PoolManager()
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
        print(f"status for requesting 'defaultKeyStatistics' of {symbol}: {r.status}")
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            defaultKeyStatistics = summary_profile["quoteSummary"]["result"][0][
                "defaultKeyStatistics"
            ]

            upsertable_data = {
                "timestamp": datetime.now().timestamp(),
                "defaultKeyStatistics": defaultKeyStatistics,
            }
            self._collection_dks.update_one(
                {"symbol": symbol}, {"$set": upsertable_data}, upsert=True
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
        _collection_assetProfile = self._db["assetProfile"]
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

        http = urllib3.PoolManager()
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
        print(f"status for requesting 'assetProfile' of {symbol}: {r.status}")
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            assetProfile = summary_profile["quoteSummary"]["result"][0]["assetProfile"]

            upsertable_data = {
                "timestamp": datetime.now().timestamp(),
                "assetProfile": assetProfile,
            }
            _collection_assetProfile.update_one(
                {"symbol": symbol}, {"$set": upsertable_data}, upsert=True
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
        _collection_financialData = self._db["financialData"]
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

        http = urllib3.PoolManager()
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
        print(f"status for requesting 'financialData' of {symbol}: {r.status}")
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            financialData = summary_profile["quoteSummary"]["result"][0][
                "financialData"
            ]

            upsertable_data = {
                "timestamp": datetime.now().timestamp(),
                "financialData": financialData,
            }
            _collection_financialData.update_one(
                {"symbol": symbol}, {"$set": upsertable_data}, upsert=True
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

        _collection_summaryDetail = self._db["summaryDetail"]
        try:
            # check if we have a price entry in the mongo-db
            summaryDetail = _collection_summaryDetail.find_one({"symbol": symbol})
            if summaryDetail is None:
                print(f"no 'summaryDetail' object for {symbol}")
            else:
                # check if the available entry is older than 5 minutes
                entry_ts = summaryDetail["timestamp"]
                current_ts = datetime.now().timestamp()

                if entry_ts + 86400 > current_ts:  # for testing 1 day
                    print(f"serving 'summaryDetail' for {symbol} from db")
                    return summaryDetail["summaryDetail"]
                else:
                    print(f"need to refresh the 'summaryDetail' in the database")

        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not write data to locale storage: ", e)

        http = urllib3.PoolManager()
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
        print(f"status for requesting 'summaryDetail' of {symbol}: {r.status}")
        summary_profile = json.loads(r.data.decode("utf-8"))

        if r.status == 200:
            summaryDetail = summary_profile["quoteSummary"]["result"][0][
                "summaryDetail"
            ]

            upsertable_data = {
                "timestamp": datetime.now().timestamp(),
                "summaryDetail": summaryDetail,
            }
            _collection_summaryDetail.update_one(
                {"symbol": symbol}, {"$set": upsertable_data}, upsert=True
            )
            return summaryDetail
        else:
            error = summary_profile["quoteSummary"]["error"]
            return {"error": error["description"]}
