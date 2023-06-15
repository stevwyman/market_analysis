from django.test import TestCase, Client
from django.contrib.messages import get_messages
from django.urls import reverse

from data.models import User, Watchlist, Security, DataProvider, Daily
from data.history_dao import History_DAO_Factory, Interval
from data.technical_analysis import SMA

"""
Note, due to limitations on the API keys, we have disabled the Polygon and Tiingo tests
also OI need to be rewritten so we do not request as many data
"""

class TechnicalAnalysis(TestCase):

    def test_sma(self) -> None:
        new_list = (1,2,3,4,5)
        sma = SMA(3)
        for i in new_list:
            sma_value = sma.add(i)
            print(f"min: {sma.getMin()} max: {sma.getMax()}")

class Onvista(TestCase):
    def setUp(self) -> None:
        onvista = DataProvider.objects.create(name="Onvista")
        return super().setUp()
    
    def test_intraday(self) -> None:
        data_provider = DataProvider.objects.get(name="Onvista")
        history_dao = History_DAO_Factory().get_online_dao(data_provider)
        result = history_dao.lookupIntraday("12105789")
        self.assertIsNotNone(result)


# disabled for commit
class Tiingo(TestCase):
    def setUp(self) -> None:
        tiingo = DataProvider.objects.create(name="Tiingo")
        manager = User.objects.create(username="Bernd", role=User.MANAGER)
        apple = Security.objects.create(
            symbol="AAPL", name="Apple Inc.", data_provider=tiingo
        )
        return super().setUp()
    
    def request_history(self) -> None:
        data_provider = DataProvider.objects.get(name="Tiingo")
        apple = Security.objects.filter(symbol="AAPL", data_provider=data_provider).first()
        self.assertIsNotNone(apple)

        history_dao = History_DAO_Factory().get_online_dao(data_provider)
        result = history_dao.lookupHistory(apple)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 10)


# disabled for commit
class Polygon(TestCase):
    def setUp(self) -> None:
        polygon = DataProvider.objects.create(name="Polygon")
        manager = User.objects.create(username="Bernd", role=User.MANAGER)
        apple = Security.objects.create(
            symbol="AAPL", name="Apple Inc.", data_provider=polygon
        )
        return super().setUp()
    
    def request_history(self) -> None:
        data_provider = DataProvider.objects.get(name="Polygon")
        apple = Security.objects.filter(symbol="AAPL", data_provider=data_provider).first()
        self.assertIsNotNone(apple)

        history_dao = History_DAO_Factory().get_online_dao(data_provider)
        result = history_dao.lookupHistory(apple)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 10)


class WatchlistViews(TestCase):
    def setUp(self) -> None:
        yahoo = DataProvider.objects.create(name="Yahoo")
        manager = User.objects.create(username="Bernd", role=User.MANAGER)
        return super().setUp()

    def test_create_watchlist(self) -> None:
        manager = User.objects.filter(username="Bernd").all()[0]

        client = Client()
        response = client.get("/data/watchlists")
        self.assertRedirects(response, "/data/login?next=/data/watchlists")
        
        client.force_login(manager)
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
        client.force_login(manager)

        response = client.post(
            "/data/watchlist_new",
            {"name": "test_name", "user": manager.pk, "visibility": "OU"},
            follow=True,
        )
        self.assertEqual(len(response.context["watchlists"]), 1)

        response = client.get("/data/watchlists")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["watchlists"]), 1)

        watchlist_id = response.context["watchlists"][0].pk

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
       
        apple = Security.objects.create(
            symbol="AAPL", name="Apple Inc.", data_provider=yahoo
        )

        history_dao = History_DAO_Factory().get_online_dao(yahoo)
        self.assertIsNotNone(history_dao)
        daily_history = history_dao.lookupHistory(
            apple, interval=Interval.DAILY, look_back=1000
        )
        self.assertIsNotNone(daily_history)
        Daily.objects.bulk_create(daily_history)

        history = apple.daily_data.all()
        self.assertIsNotNone(history)

        client = Client(enforce_csrf_checks=True)
        response = client.post("/data/tp/" + str(apple.pk), data={"view": "sd"})
        self.assertEqual(response.status_code, 403)  ## TODO csrf test


class YahooYCL(TestCase):
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
            for security in watchlist.securities.all():
                self.assertIsNotNone(security)
                self.assertIsNotNone(security.watchlists.all())

    def test_historic_import(self):
        data_provider = DataProvider.objects.get(name="Yahoo")
        history_dao = History_DAO_Factory().get_online_dao(data_provider)
        watchlist = Watchlist.objects.get(name="Test List")

        for security in watchlist.securities.all():
            result = history_dao.lookupHistory(
                security, interval=Interval.DAILY, look_back=10
            )
            Daily.objects.bulk_create(result)

        for security in watchlist.securities.all():
            daily = security.daily_data
            self.assertGreaterEqual(daily.count(), 4)
           
    def test_read_quote_summary(self):
        data_provider = DataProvider.objects.get(name="Yahoo")
        history_dao = History_DAO_Factory().get_online_dao(data_provider)

        result = history_dao.lookupSymbol("AAPL")
        self.assertEqual(result["country"], "United States")

        result = history_dao.lookupSymbol("AAPP")
        self.assertEqual(result["error"], "Quote not found for ticker symbol: AAPP")

    def test_read_price(self):
        data_provider = DataProvider.objects.get(name="Yahoo")
        history_dao = History_DAO_Factory().get_online_dao(data_provider)

        result = history_dao.lookupPrice("AAPL")
        self.assertEqual(result["shortName"], "Apple Inc.")

        result = history_dao.lookupPrice("AAPP")
        self.assertEqual(result["error"], "Quote not found for ticker symbol: AAPP")


from data.views import underlyings
from data.open_interest import next_expiry_date, get_max_pain_history, update_data


# disabled for commit
class OI(TestCase):
    def _read_oi_dax(self) -> None:
        product = underlyings["DAX"]
        self.assertIsNotNone(product)
        expiry_date = next_expiry_date()
        self.assertIsNotNone(expiry_date)
        parameter = {"product": product, "expiry_date": expiry_date}

        max_pain_over_time = sorted(
            get_max_pain_history(parameter), key=lambda x: x[0], reverse=False
        )

        if len(max_pain_over_time) > 0:
            pass
        else:
            update_data(parameter)
            max_pain_over_time = sorted(
                get_max_pain_history(parameter), key=lambda x: x[0], reverse=False
            )

        self.assertGreater(len(max_pain_over_time), 0)
