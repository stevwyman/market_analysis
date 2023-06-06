from django import forms
from django.forms import TextInput

from .models import Watchlist, Security, Limit


class WatchlistForm(forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ["name", "user", "visibility"]
        widgets = {
            "name": TextInput(
                attrs={"placeholder": "new watchlist name"}
            ),
            "user": forms.HiddenInput()
        }


class SecurityForm(forms.ModelForm):

    def clean_symbol(self):
        return self.cleaned_data["symbol"].upper()
    
    class Meta:
        model = Security
        fields = ["symbol", "data_provider"]
        widget = {
            "symbol": TextInput(
                attrs={"placeholder": "symbol"}
            )
        }

class LimitForm(forms.ModelForm):
    class Meta:
        model = Limit
        fields = ["user", "security", "price", "comment", "role"]
        widgets = {
            "user": forms.HiddenInput(),
            "security": forms.HiddenInput()
            }
        