# from alerting.models import Alert
from alerting.logic import generate_alerts_wrapper

from django.core.management.base import BaseCommand

import datetime
import random
import pytz


class Command(BaseCommand):
    def handle(self, *args, **options):
        # for _ in range(2):
        #     alert = Alert()
        #     alert.generated_time = datetime.datetime.now(pytz.timezone('Europe/Prague'))
        #     alert.referenced_time = alert.generated_time + datetime.timedelta(minutes=random.randint(5, 4320))
        #     alert.symbol = random.choice(['BTC', 'ETH', 'BNB', 'ADA', 'XRP', 'DOGE', 'DOT', 'UNI', 'BCH', 'LTC'])
        #     alert.current_exchange_rate = random.uniform(9, 12)
        #     alert.referenced_exchange_rate = random.uniform(10, 11)
        #     alert.save()
        #
        # print("Test alerts successfully generated.")

        generate_alerts_wrapper()
        return  # Probably required by Heroku so that app can be shut down
