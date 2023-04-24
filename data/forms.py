from django import forms
from django.forms import TextInput

from .models import Watchlist, Security


class WatchlistForm(forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ["name", "user", "visibility"]
        widgets = {
            "name": TextInput(
                attrs={"placeholder": "new watchlist name"}
            )
        }


class SecurityForm(forms.ModelForm):
    class Meta:
        model = Security
        fields = ["symbol", "data_provider"]
        widget = {
            "symbol": TextInput(
                attrs={"placeholder": "symbol"}
            )
        }
