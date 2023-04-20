from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _



# Create your models here.

"""
A User is required to assign roles and then to connect to to watchlists
"""
class User(AbstractUser):
    MANAGER = 1
    PREMIUM = 2
    BASIC = 3 
      
    ROLE_CHOICES = (
        (MANAGER, "Manager"),
        (PREMIUM, "Premium"),
        (BASIC, "Basic"),
    )
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, blank=False, null=False)
  

class Security(models.Model):
    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=12)
    wkn = models.CharField(max_length=12)
    isin = models.CharField(max_length=24)

    type # stock, index, commodity, ...

    industry = models.CharField(max_length=255)
    sector = models.CharField(max_length=255)
    country = models.CharField(max_length=255)

    exchange = models.CharField(max_length=32) # XETRA, NYSE
    currency = models.CharField(max_length=6) # EUR, USD, HKD, JPN ...
    currency_symbol = models.CharField(max_length=6) # $, €, ...

    def __str__(self) -> str:
          return self.symbol

class DataProvider(models.Model):
    name = models.TextField()

class Watchlist(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Visibility(models.TextChoices):
        USER = "OU", _("only by user")
        PREMIUM = "AP", _("for all premium user")
        ALL = "AU", _("for all user")

    visibility = models.CharField(
        max_length=2,
        choices=Visibility.choices,
        default=Visibility.USER
    )

    securities = models.ManyToManyField("Security", related_name="watchlists")

    data_provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    def serialize(self):
        return{
            "id": self.id,
            "name": self.name,
            "user": self.user,
            "visibility": self.visibility,
            "data_provider": self.data_provider
        }

    class Meta:
        ordering = ["name"]


class HistoricData(models.Model):
    security = models.ForeignKey(Security, on_delete=models.CASCADE)
    date = models.DateField()
    data_provider = models.ForeignKey(DataProvider, on_delete=models.CASCADE)
    open_price = models.DecimalField(max_digits=7, decimal_places=4) 
    high_price = models.DecimalField(max_digits=7, decimal_places=4) 
    low = models.DecimalField(max_digits=7, decimal_places=4) 
    close  = models.DecimalField(max_digits=7, decimal_places=4) 
    volume = models.PositiveIntegerField()
    
    class Meta:
        abstract = True


class DailyData(HistoricData):
    
    class Meta(HistoricData.Meta):
                constraints = [
            models.UniqueConstraint(
                fields=["security", "data_provider", "date"], name='unique_sec_provider_date_daily_combination'
            )
        ]

class WeeklyData(HistoricData):
    
    class Meta(HistoricData.Meta):
                constraints = [
            models.UniqueConstraint(
                fields=["security", "data_provider", "date"], name='unique_sec_provider_date_weekly_combination'
            )
        ]

class MonthlyData(HistoricData):
    
    class Meta(HistoricData.Meta):
                constraints = [
            models.UniqueConstraint(
                fields=["security", "data_provider", "date"], name='unique_sec_provider_date_monthly_combination'
            )
        ]
