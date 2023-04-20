import json
import urllib3


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
