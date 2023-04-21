from django.test import TestCase

from data.models import User, Watchlist, Security, DataProvider, Daily
from data.OnlineDAO import YahooOnlineDAO, Interval


# Create your tests here.

class YahooYCL(TestCase):

    dao = YahooOnlineDAO()

    def setUp(self) -> None:

        yahoo = DataProvider.objects.create(name="Yahoo")
        manager = User.objects.create(role=User.MANAGER)

        apple = Security.objects.create(symbol="AAPL", name="Apple Inc.", data_provider=yahoo)
        microsoft = Security.objects.create(symbol="MSFT", name="Microsoft Inc.", data_provider=yahoo)
        alphabet = Security.objects.create(symbol="GOOGL", name="Alphabet Inc.", data_provider=yahoo)

        test_list_1 = Watchlist.objects.create(name="Test List", user=manager, visibility="USER")

        test_list_1.securities.add(apple)
        test_list_1.securities.add(microsoft)

        test_list_2 = Watchlist.objects.create(name="Test List with google", user=manager, visibility="USER")

        test_list_2.securities.add(apple)
        test_list_2.securities.add(microsoft)
        test_list_2.securities.add(alphabet)

        return super().setUp()
    
    def test_watchlist(self):

        watchlists = Watchlist.objects.all()
        
        for watchlist in watchlists:
            print(f"listing securities in {watchlist.name}")
            for security in watchlist.securities.all():
                print(security)
                print(security.watchlists.all())

    def test_historic_import(self):

        watchlist = Watchlist.objects.get(name="Test List")

        for security in watchlist.securities.all():
            result = self.dao.lookupHistory(security, interval=Interval.DAILY, look_back=10)
            Daily.objects.bulk_create(result)

        for security in watchlist.securities.all():
            daily = security.daily_data
            print(f"{security.symbol} daily has {daily.count()} entries")


    def test_read_quote_summary(self):

        result = self.dao.lookupSymbol("AAPL")
        self.assertEqual(result["country"], "United States")

        result = self.dao.lookupSymbol("AAPP")
        self.assertEqual(result["error"], "Quote not found for ticker symbol: AAPP")

    def test_read_price(self):

        result = self.dao.lookupPrice("AAPL")
        self.assertEqual(result["shortName"], "Apple Inc.")

        result = self.dao.lookupPrice("AAPP")
        self.assertEqual(result["error"], "Quote not found for ticker symbol: AAPP")