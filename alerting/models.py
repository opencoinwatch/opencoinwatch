from opencoinwatch import config
from alerting import common_utils
from alerting import production

from django.db.models import Q
from django.db import models

import datetime
import pytz


class Alert(models.Model):
    generated_time = models.DateTimeField()
    referenced_time = models.DateTimeField()
    symbol = models.CharField(max_length=64)
    current_exchange_rate = models.FloatField()
    referenced_exchange_rate = models.FloatField()
    published = models.BooleanField(default=False)
    declined = models.BooleanField(default=False)
    published_time = models.DateTimeField(null=True, blank=True)
    published_text = models.TextField(blank=True)

    def publish(self):
        assert self.is_validating()
        self.published = True
        self.published_time = datetime.datetime.now(pytz.timezone('Europe/Prague'))
        text = self.get_text()
        production.post_tweet(text)
        production.send_pushover_notification(text)
        self.published_text = text
        self.save()

    def prepare_for_validation(self):
        alerts_existed = False
        existing_alerts = Alert.get_all_validating_alerts(self.symbol)
        if existing_alerts.exists():
            existing_alerts.delete()
            alerts_existed = True

        self.save()

        if not alerts_existed:
            production.send_pushover_notification("New alert waiting for validation.")

    def decline(self):
        assert self.is_validating()
        self.declined = True
        self.save()

    def is_validating(self):
        return self.published == False and self.declined == False

    def get_importance(self):
        percentual_change = self.get_percentual_change()
        limit = common_utils.percentage_limit(self.get_time_difference_minutes())
        return abs(percentual_change / limit)

    def get_importance_with_handicap(self):
        importance = self.get_importance()
        handicap = self.get_handicap()
        return importance / handicap

    def get_handicap(self):
        return Alert.get_handicap_for_symbol(self.symbol, self.current_exchange_rate)

    def get_percentual_change(self):
        relative_change = self.current_exchange_rate / self.referenced_exchange_rate
        percentual_change = (relative_change - 1) * 100
        return percentual_change

    def get_time_difference_minutes(self):
        return (self.generated_time - self.referenced_time).total_seconds() / 60

    def get_emoji(self):
        if self.get_percentual_change() > 0:
            return "☀️"  # Sunny
        elif self.get_importance_with_handicap() < 2:
            return "☁️"  # Cloudy
        else:
            return "🌧️"  # Rain

    def get_text(self):
        percentual_change_raw = self.get_percentual_change()

        symbol = self.symbol
        direction = "UP" if percentual_change_raw > 0 else "DOWN"
        emoji = self.get_emoji()
        percentual_change = common_utils.smart_float_format(abs(percentual_change_raw))
        time_difference = common_utils.smart_time_duration_format(self.get_time_difference_minutes())
        exchange_rate = common_utils.smart_float_format(self.current_exchange_rate)
        hashtags = " ".join([f"#{tag}" for tag in config.SYMBOLS[self.symbol]['hashtags']])
        link = f"https://coinmarketcap.com/currencies/{config.SYMBOLS[self.symbol]['coinmarketcap']}/"

        return f"{symbol} {direction} {emoji} by {percentual_change}% in the last {time_difference}, now at ${exchange_rate} {hashtags} {link}"

    @staticmethod
    def get_last_published_or_declined_alert_generated_time(symbol):
        symbols_match = Q(symbol=symbol)
        is_published = Q(published=True)
        is_declined = Q(declined=True)
        queryset = Alert.objects.filter(symbols_match & (is_published | is_declined)).order_by('-generated_time')
        if queryset.exists():
            return queryset[0].generated_time
        return None

    @staticmethod
    def get_last_published_alert_published_time():
        is_published = Q(published=True)
        published_time_not_null = Q(published_time__isnull=False)
        queryset = Alert.objects.filter(is_published & published_time_not_null).order_by('-published_time')
        if queryset.exists():
            return queryset[0].published_time
        return None

    @staticmethod
    def get_all_validating_alerts(symbol):
        symbols_match = Q(symbol=symbol)
        not_published = Q(published=False)
        not_declined = Q(declined=False)
        return Alert.objects.filter(symbols_match & not_published & not_declined)

    @staticmethod
    def get_handicap_for_symbol(symbol, exchange_rate):
        symbol_market_cap = Alert.get_market_cap_for_symbol(symbol, exchange_rate)
        bitcoin_market_cap = Alert.get_market_cap_for_symbol('BTC', Alert.get_latest_bitcoin_exchange_rate())
        return common_utils.rectified_root(bitcoin_market_cap / symbol_market_cap, degree=4)

    @staticmethod
    def get_market_cap_for_symbol(symbol, exchange_rate):
        supply = config.SYMBOLS[symbol]['supply']
        return supply * exchange_rate

    @staticmethod
    def get_latest_bitcoin_exchange_rate():
        is_bitcoin = Q(symbol='BTC')
        is_published = Q(published=True)
        queryset = Alert.objects.filter(is_bitcoin & is_published).order_by('-published_time')
        if not queryset.exists():
            print("Warning: Using fallback Bitcoin exchange rate.")
            return config.FALLBACK_BITCOIN_EXCHANGE_RATE
        return queryset[0].current_exchange_rate


class Job(models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.delete_old_jobs()

    def delete_old_jobs(self):
        old_jobs = Job.objects.order_by('-start_time')[config.MAX_JOBS_IN_DATABASE:]
        for old_job in old_jobs:
            old_job.delete()

    def succeeded(self):
        self.end_time = datetime.datetime.now(pytz.timezone('Europe/Prague'))
        self.success = True
        self.save()

    def failed(self):
        self.end_time = datetime.datetime.now(pytz.timezone('Europe/Prague'))
        self.success = False
        self.save()

    def get_duration(self):
        if not self.end_time:
            return None
        return round((self.end_time - self.start_time).total_seconds(), 1)
