from data.models import Security, Daily, DailyUpdate
from data.OnlineDAO import Online_DAO_Factory
from django_cron import CronJobBase, Schedule
from django.db import DatabaseError, transaction
from datetime import date

import time

class UpdateDailyJob(CronJobBase):

    RUN_AT_TIMES = ["06:00"]
    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = "data.updateDaily"

    def do(self):
        all_securities = Security.objects.all()
        counter = 0
        for security in all_securities:
            _today = date.today()
            last_updated = security.dailyupdate_data.all().first()

            if last_updated is not None:
                if last_updated.date == _today:
                    print(f"no update required for {security}")
                    continue

            online_dao = Online_DAO_Factory().get_online_dao(security.data_provider)

            # request new history from online dao
            result = online_dao.lookupHistory(security=security, look_back=5000)
            if len(result) > 10:
                try:
                    with transaction.atomic():
                        # drop current history
                        Daily.objects.filter(security=security).delete()
                        try:
                            DailyUpdate.objects.get(security=security).delete()
                        except:
                            pass

                        # crate new history
                        Daily.objects.bulk_create(result)
                        DailyUpdate.objects.create(security=security)
                        
                except DatabaseError as db_error:
                    print(db_error)

            time.sleep(5)

