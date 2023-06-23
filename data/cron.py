from logging import getLogger
from data.models import DataProvider

logger = getLogger(__name__)

def my_cron_job():
    # your functionality goes here 

    polygon = DataProvider.objects.create(name="Polygon")
    logger.info("cron running")