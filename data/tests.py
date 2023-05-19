from django.test import TestCase, Client
from django.contrib.messages import get_messages

from data.models import User, Watchlist, Security, DataProvider, Daily
from data.OnlineDAO import YahooDAO, Interval

# Create your tests here.
class WatchlistViews(TestCase):
    def setUp(self) -> None:
        yahoo = DataProvider.objects.create(name="Yahoo")
        manager = User.objects.create(username="Bernd", role=User.MANAGER)
        return super().setUp()

    def test_create_watchlist(self) -> None:
        manager = User.objects.filter(username="Bernd").all()[0]

        client = Client()
        response = client.get("/data/watchlists")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["watchlists"]), 0)

        response = client.get("/data/watchlist_new")
        self.assertEqual(response.status_code, 200)

        response = client.post(
            "/data/watchlist_new",
            {"name": "test_name", "user": manager.pk, "visibility": "OU"},
            follow=True,
        )
        self.assertEqual(len(response.context["watchlists"]), 1)

    def test_add_security_to_watchlist(self) -> None:
        manager = User.objects.filter(username="Bernd").all()[0]

        client = Client()

        response = client.post(
            "/data/watchlist_new",
            {"name": "test_name", "user": manager.pk, "visibility": "OU"},
            follow=True,
        )
        self.assertEqual(len(response.context["watchlists"]), 1)

        response = client.get("/data/watchlists")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["watchlists"]), 1)

        watchlist_id = response.context["watchlists"].first().pk
        print(f"using watchlist id: {watchlist_id}")

        response = client.get("/data/security_new/" + str(watchlist_id))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["form"])
        self.assertEqual(response.context["watchlist"].pk, watchlist_id)

        response = client.post(
            "/data/security_new/" + str(watchlist_id),
            {"symbol": "GS", "watchlist_id": watchlist_id},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Form is not valid")

        data_provider = DataProvider.objects.filter(name="Yahoo").first()

        response = client.post(
            "/data/security_new/" + str(watchlist_id),
            {
                "symbol": "GS",
                "watchlist_id": watchlist_id,
                "data_provider": data_provider.pk,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["watchlist_entries"]), 1)

    def test_technical_parameter(self) -> None:
        yahoo = DataProvider.objects.create(name="Yahoo")
        manager = User.objects.create(role=User.MANAGER)

        apple = Security.objects.create(
            symbol="AAPL", name="Apple Inc.", data_provider=yahoo
        )

        dao = YahooDAO()
        self.assertIsNotNone(dao)
        daily_history = dao.lookupHistory(
                apple, interval=Interval.DAILY, look_back=1000
            )
        self.assertIsNotNone(daily_history)
        Daily.objects.bulk_create(daily_history)

        history = apple.daily_data.all()
        self.assertIsNotNone(history)

        client = Client(enforce_csrf_checks=True)
        response = client.post("/data/tp/" + str(apple.pk), data={"view": "sd"})
        self.assertEqual(response.status_code, 403) ## TODO csrf test
        print(response)

class YahooYCL(TestCase):
    dao = YahooDAO()

    def setUp(self) -> None:
        yahoo = DataProvider.objects.create(name="Yahoo")
        manager = User.objects.create(role=User.MANAGER)

        apple = Security.objects.create(
            symbol="AAPL", name="Apple Inc.", data_provider=yahoo
        )
        microsoft = Security.objects.create(
            symbol="MSFT", name="Microsoft Inc.", data_provider=yahoo
        )
        alphabet = Security.objects.create(
            symbol="GOOGL", name="Alphabet Inc.", data_provider=yahoo
        )

        test_list_1 = Watchlist.objects.create(
            name="Test List", user=manager, visibility="USER"
        )

        test_list_1.securities.add(apple)
        test_list_1.securities.add(microsoft)

        test_list_2 = Watchlist.objects.create(
            name="Test List with google", user=manager, visibility="USER"
        )

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
            result = self.dao.lookupHistory(
                security, interval=Interval.DAILY, look_back=10
            )
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
