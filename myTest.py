from data.OnlineDAO import YahooDAO, Interval
from io import StringIO
import csv


online_dao = YahooDAO()

# print(online_dao.lookupSymbol("AAPL"))

result = online_dao.lookupHistory("AAPL", interval=Interval.DAILY, look_back=10)

print(result)