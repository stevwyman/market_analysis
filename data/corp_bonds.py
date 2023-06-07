import pymongo
import time
import urllib3
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from lxml import etree
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from data.technical_analysis import EMA

from data.meta_dao import MetaData_Factory

from logging import getLogger

logger = getLogger(__name__)


FINRA_DATE_FORMAT = "%m/%d/%Y"
LOCAL_DATE_FORMAT = "%Y%m%d"


class OnlineReader:
    def __init__(self):
        # open a connection to a URL using urllib3
        self._http = urllib3.PoolManager()

        options = Options()
        options.add_argument("--headless")
        # options.add_argument("--ignore-ssl-errors=yes")
        # options.add_argument("--ignore-certificate-errors")
        # using docker
        # options.binary_location = '/browser/firefox'
        # browser = webdriver.Firefox(executable_path='/drivers/geckodrive', options=options)

        # local
        # browser = webdriver.Firefox(options=options)

        # for using the docker image: http://standalone-firefox:4444/wd/hub
        # for use in dev http://localhost:4444/wd/hub
        browser = webdriver.Remote(
            command_executor='http://standalone-firefox:4444/wd/hub',
            options=options
        )


        browser.get(
            "https://finra-markets.morningstar.com/BondCenter/TRACEMarketAggregateStats.jsp"
        )

        all_cookies = browser.get_cookies()
        if len(all_cookies) < 1:
            raise ValueError("Could not get cookie")

        self.__cookie__ = ""
        for cookie in all_cookies:
            self.__cookie__ += cookie["name"] + "=" + cookie["value"] + ";"

        logger.debug(f"cookie: {self.__cookie__}")

        try:
            browser.close()
            browser.quit()
        except:
            logger.warn("Could not close browser")

    def return_data(self, data: str) -> dict:
        """
        takes a str and parses it to return an dictionary object for a given date

        """

        table = etree.HTML(str(data))

        # file date
        file_date = table.find(".//table").attrib["data-filedate"]
        # print(f"file_date: {file_date}")

        file_date_p = datetime.strptime(file_date, FINRA_DATE_FORMAT)
        file_date = int(datetime.strftime(file_date_p, "%Y%m%d"))

        # headers
        headers = [th.text for th in table.findall(".//tr/th")]
        # print(headers)

        columns = len(headers)

        data = list()

        row_description = table.findall(".//tbody/th")
        for description in row_description:
            row = list()
            row.append(description.text)
            data.append(row)

        entries = table.findall(".//tbody/td")

        entry = 0
        row = 0
        while entry < len(entries):
            for column in range(columns - 1):
                # add the current entry to the list of entries for this row
                data[row].append(entries[entry].text)
                # next entry
                entry += 1
            # next row
            row += 1

        # print(tabulate(data,headers = headers,tablefmt='fancy_grid'))

        data_dict = {}
        for column in range(1, 5):
            entry_dict = {}
            for row in range(6):
                entry_dict[data[row][0]] = int(data[row][column])
            data_dict[headers[column]] = entry_dict

        # print(data_dict)

        entries = len(data_dict)
        if entries == 0:
            print("... no data available")
        else:
            print(f"... received {entries} entries")

        return {"date": file_date, "bond_data": data_dict}

    def request_data(self, date: datetime) -> dict:
        """
        tries to grab data from the morningstar.com page and returns the pure data as str

        https://finra-markets.morningstar.com/transferPage.jsp?
            path=http://muni-internal.morningstar.com/public/MarketBreadth/C
            &date=03/08/2023
            &_=1678553779148

        """
        url = "https://finra-markets.morningstar.com/transferPage.jsp?path=http://muni-internal.morningstar.com/public/MarketBreadth/C"

        url += "&date=" + datetime.strftime(date, FINRA_DATE_FORMAT)

        date = datetime.utcnow() - datetime(1970, 1, 1)
        seconds = date.total_seconds()
        milliseconds = round(seconds * 1000)

        url += "&_=" + str(milliseconds)

        response = self._http.request("GET", url, headers={"Cookie": self.__cookie__})
        logger.debug(f"Response for {response.geturl()}: {response.status} ... ")
        # print(response.data)

        finra_html = response.data.decode("utf-8")
        parsed_html = BeautifulSoup(finra_html, features="lxml")
        # print(parsed_html)

        if parsed_html.body == None:
            raise RuntimeError("invalid response received - empty dataset")

        data_table = parsed_html.body.find("table")

        return self.return_data(data_table)


class LocaleDAO:
    def __init__(self):
        _db = MetaData_Factory().db("market_analysis")
        self._collection = _db["finra_bonds"]

    def write(self, bond_data: dict) -> None:
        file_date = bond_data["date"]
        data = bond_data["bond_data"]
        try:
            if len(list(self._collection.find({"date": file_date}))) > 0:
                logger.debug(f"Entry exists already.")
            else:
                logger.debug(f"Adding new entry for {file_date}")
                self._collection.insert_one(bond_data)
        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error("Could not write data to locale storage: ", e)
        except KeyError:
            pass

    def read_all(self) -> list[dict]:
        """
        returns a list of all entries in the database sorted by date
        """
        try:
            cursor = self._collection.find().sort([("date", 1)])
            return list(cursor)
        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error("Could not read data from locale storage: ", e)
            return list()
        except KeyError as ke:
            return list()

    def read(self, limit: int) -> list[dict]:
        """
        returns a list of all entries in the database sorted by date
        """
        try:
            cursor = self._collection.find().sort([("date", -1)]).limit(limit)
            return sorted(list(cursor), key=lambda d: d["date"])
        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error("Could not read data from locale storage: ", e)
            return list()
        except KeyError as ke:
            return list()

    def read_by_dates(self, start_date: int, end_date: int) -> list[dict]:
        """
        returns a list of all entries in the database sorted by date
        """
        try:
            query = {"date": {"$gt": start_date, "$lt": end_date}}
            cursor = self._collection.find(query).sort([("date", -1)])
            return sorted(list(cursor), key=lambda d: d["date"])
        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error("Could not read data from locale storage: ", e)
            return list()
        except KeyError as ke:
            return list()

    def read_by_date(self, date: int) -> dict:
        """
        using the given date string, find the matching Market Aggregate Information
        """
        try:
            return self._collection.find_one({"date": date})
        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error("Could not read data from locale storage: ", e)
            return dict()
        except KeyError:
            return dict()

    def most_recent(self) -> datetime:
        recent_entry = self.read(1)
        if len(recent_entry) == 1:
            date_as_int = recent_entry[0]["date"]
            return datetime.strptime(str(date_as_int), LOCAL_DATE_FORMAT)
        else:
            logger.warn("Currently no entries available, hence requesting new ...")
            return datetime.today() - timedelta(days=400)

    def close(self):
        self._client.close


def update() -> None:
    """
    checks the latest entry in the local data storage and then updates all missing data until today
    """
    local_dao = LocaleDAO()
    most_recent_date = local_dao.most_recent()
    today = datetime.now()
    update_range(
        datetime.strftime(most_recent_date, FINRA_DATE_FORMAT),
        datetime.strftime(today, FINRA_DATE_FORMAT),
    )


def update_range(from_date: str, to_date: str) -> None:
    """
    updates the data storage with the entries specified by parameters
    parameters need to come in the following format: "mm/dd/yyyy" the finra data format
    """
    weekend = set([5, 6])
    start: datetime = datetime.strptime(from_date, FINRA_DATE_FORMAT)
    d: datetime = start
    end: datetime = datetime.strptime(to_date, FINRA_DATE_FORMAT)

    delta: timedelta = timedelta(days=1)

    local_dao: LocaleDAO = LocaleDAO()
    online_dao: OnlineReader = OnlineReader()

    logger.info(f"collecting from {from_date} to {to_date}")

    while d <= end:
        if d.weekday() not in weekend:
            date_str = d.strftime(LOCAL_DATE_FORMAT)
            logger.info(f"Checking {date_str}")

            # check if the entry is already existing
            data = local_dao.read_by_date(int(date_str))
            if data is None:
                try:
                    online_data = online_dao.request_data(d)
                    if d.strftime("%Y%m%d") == str(online_data["date"]):
                        local_dao.write(online_data)
                except RuntimeError as rt:
                    logger.warn(f"Could not get data for {d}: {rt}")
                time.sleep(4)
        d += delta


def read_bonds_data(type: str, ad_ema=39) -> dict:
    local_dao = LocaleDAO()
    ad_history = local_dao.read(250)

    previous_ad = 100000
    ad_line = list()
    trend_line = list()
    trend = EMA(ad_ema)
    for ad_data in ad_history:
        
        adv = ad_data["bond_data"][type]["Advances"]
        dec = ad_data["bond_data"][type]["Declines"]
        
        # date comes as str in form of yyyymmdd
        date = datetime.strptime(str(ad_data["date"]), LOCAL_DATE_FORMAT)

        current_ad = adv - dec + previous_ad
        ad_line.append({"time": str(date), "value": current_ad})

        trend_value = trend.add(current_ad)
        if trend_value is not None:
            trend_line.append({"time": str(date), "value": trend_value})
        
        previous_ad = current_ad

    return {"ad": ad_line, "trend": trend_line, "type":type}
