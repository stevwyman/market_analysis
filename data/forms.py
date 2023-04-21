from django import forms
from django.forms import TextInput

from .models import Watchlist, Security

class WatchlistForm(forms.ModelForm):

    class Meta:
        model = Watchlist
        fields = "__all__"
        widgets = {

        }