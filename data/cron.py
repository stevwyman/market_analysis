from logging import getLogger
from .models import DataProvider
import time 
import datetime


logger = getLogger(__name__)

def my_cron_job():
    now = time.time()
    data_provider = DataProvider(
            name=now, description=datetime.strptime(str(now), '%Y-%m-%d %H:%M:%S') 
        )
    data_provider.save()
    print("my cron is running")
    logger.info("my cron is running")