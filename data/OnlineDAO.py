import json
import csv
import urllib3
from io import StringIO
import decimal

from enum import Enum
from time import time
from datetime import datetime, timedelta

from data.models import Daily, Security


class Interval(Enum):
    HOURLY = "1h"
    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"


class YahooOnlineDAO:
    def __init__(self) -> None:
        pass

    def lookupSymbol(self, symbol) -> dict:
        """
        returns, if found, the "summaryProfile" data set

        {"quoteSummary":{"result":[{"price":{"maxAge":1,"preMarketChangePercent":{"raw":-0.00954487,"fmt":"-0.95%"},"preMarketChange":{"raw":-1.60001,"fmt":"-1.60"},"preMarketTime":1681997399,"preMarketPrice":{"raw":166.03,"fmt":"166.03"},"preMarketSource":"FREE_REALTIME","postMarketChange":{},"postMarketPrice":{},"regularMarketChangePercent":{"raw":-0.0011931766,"fmt":"-0.12%"},"regularMarketChange":{"raw":-0.2000122,"fmt":"-0.20"},"regularMarketTime":1682013624,"priceHint":{"raw":2,"fmt":"2","longFmt":"2"},"regularMarketPrice":{"raw":167.43,"fmt":"167.43"},"regularMarketDayHigh":{"raw":167.87,"fmt":"167.87"},"regularMarketDayLow":{"raw":165.91,"fmt":"165.91"},"regularMarketVolume":{"raw":28145554,"fmt":"28.15M","longFmt":"28,145,554.00"},"averageDailyVolume10Day":{},"averageDailyVolume3Month":{},"regularMarketPreviousClose":{"raw":167.63,"fmt":"167.63"},"regularMarketSource":"FREE_REALTIME","regularMarketOpen":{"raw":166.09,"fmt":"166.09"},"strikePrice":{},"openInterest":{},"exchange":"NMS","exchangeName":"NasdaqGS","exchangeDataDelayedBy":0,"marketState":"REGULAR","quoteType":"EQUITY","symbol":"AAPL","underlyingSymbol":null,"shortName":"Apple Inc.","longName":"Apple Inc.","currency":"USD","quoteSourceName":"Nasdaq Real Time Price","currencySymbol":"$","fromCurrency":null,"toCurrency":null,"lastMarket":null,"volume24Hr":{},"volumeAllCurrencies":{},"circulatingSupply":{},"marketCap":{"raw":2649060540416,"fmt":"2.65T","longFmt":"2,649,060,540,416.00"}}}],"error":null}}
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

        summary_profile = json.loads(r.data.decode("utf-8"))

        print(f"status for requesting 'price' of {symbol}: {r.status}")

        if r.status == 200:
            return summary_profile["quoteSummary"]["result"][0]["price"]
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
        for row in reader:
            print(row)
            date_str = row["Date"]
            open_str = row["Open"]
            high_str = row["High"]
            low_str = row["Low"]
            close_adj_str = row["Adj Close"]
            close_str = row["Close"]
            volume_str = row["Volume"]

            entry = Daily(
                date = datetime.strptime(date_str, "%Y-%m-%d").date(),
                security = security,

                open_price = decimal.Decimal(open_str),
                high_price = decimal.Decimal(high_str),
                low = decimal.Decimal(low_str),
                close = decimal.Decimal(close_str),
                adj_close = decimal.Decimal(close_adj_str),
                volume = int(volume_str)
            )

            historic_entries.append(entry)

        return historic_entries
