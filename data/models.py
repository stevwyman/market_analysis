from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


# Create your models here.


class User(AbstractUser):
    """
    A User is required to assign roles and then to connect to to watchlists
    """

    MANAGER = 1
    PREMIUM = 2
    BASIC = 3

    ROLE_CHOICES = (
        (MANAGER, "Manager"),
        (PREMIUM, "Premium"),
        (BASIC, "Basic"),
    )
    role = models.PositiveSmallIntegerField(
        choices=ROLE_CHOICES, blank=False, null=False, default=BASIC
    )


class DataProvider(models.Model):
    name = models.CharField(max_length=24, null=False, blank=False)
    description = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class Security(models.Model):
    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=12, null=False, blank=False)
    wkn = models.CharField(max_length=12)
    isin = models.CharField(max_length=24)

    data_provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)

    type = models.CharField(max_length=24)

    industry = models.CharField(max_length=255)
    sector = models.CharField(max_length=255)
    country = models.CharField(max_length=255)

    exchange = models.CharField(max_length=32)  # XETRA, NYSE
    currency = models.CharField(max_length=6)  # EUR, USD, HKD, JPN ...
    currency_symbol = models.CharField(max_length=6)  # $, €, ...

    def __str__(self) -> str:
        return self.symbol

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["symbol", "data_provider"],
                name="unique_symbol_data_provider_combination",
            )
        ]


class Watchlist(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Visibility(models.TextChoices):
        USER = "OU", _("only by user")
        PREMIUM = "AP", _("for all premium user")
        ALL = "AU", _("for all user")

    visibility = models.CharField(
        max_length=2, choices=Visibility.choices, default=Visibility.USER
    )

    securities = models.ManyToManyField(Security, related_name="watchlists")

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "user": self.user,
            "visibility": self.visibility,
        }

    class Meta:
        ordering = ["name"]


class HistoricData(models.Model):
    security = models.ForeignKey(
        Security,
        on_delete=models.CASCADE,
        related_name="%(class)s_%(app_label)s",
    )
    date = models.DateField(null=False, blank=False)
    open_price = models.DecimalField(max_digits=16, decimal_places=6)
    high_price = models.DecimalField(max_digits=16, decimal_places=6)
    low = models.DecimalField(max_digits=16, decimal_places=6)
    close = models.DecimalField(max_digits=16, decimal_places=6)
    adj_close = models.DecimalField(max_digits=16, decimal_places=6)
    volume = models.PositiveIntegerField()

    def __str__(self):
        return self.security.name + " " + str(self.date) + " " + str(self.close)

    class Meta:
        abstract = True
        ordering = ["-date"]


class HistoryLastUpdate(models.Model):
    security = models.ForeignKey(
        Security,
        on_delete=models.CASCADE,
        related_name="%(class)s_%(app_label)s",
    )

    date = models.DateField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["security"]


class Daily(HistoricData):
    class Meta(HistoricData.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["security", "date"], name="unique_sec_date_daily_combination"
            )
        ]


class DailyUpdate(HistoryLastUpdate):
    class Meta(HistoryLastUpdate.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["security", "date"], name="unique_sec_update_daily_combination"
            )
        ]


class Weekly(HistoricData):
    class Meta(HistoricData.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["security", "date"],
                name="unique_sec_date_weekly_combination",
            )
        ]


class WeeklyUpdate(HistoryLastUpdate):
    class Meta(HistoryLastUpdate.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["security", "date"], name="unique_sec_update_weekly_combination"
            )
        ]


class Monthly(HistoricData):
    class Meta(HistoricData.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["security", "date"],
                name="unique_sec_date_monthly_combination",
            )
        ]


class MonthlyUpdate(HistoryLastUpdate):
    class Meta(HistoryLastUpdate.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["security", "date"],
                name="unique_sec_update_monthly_combination",
            )
        ]
