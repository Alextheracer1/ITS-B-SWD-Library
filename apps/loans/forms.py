"""
Formulare & Eingabevalidierung für Use Case 1: Medium ausleihen
Verantwortlich: Alexander Graf (1. Autor)
"""

from django import forms
from apps.core.models import Patron, Media, Reservation


class LoanRequestForm(forms.Form):
    """
    Formular zur Ausleihe eines Mediums über Web / Kiosk.
    """
    patron = forms.ModelChoiceField(
        queryset=Patron.objects.all(),
        label="Bibliothekskunde",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    media = forms.ModelChoiceField(
        queryset=Media.objects.all(),
        label="Gewünschtes Medium (Titel)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reservation = forms.ModelChoiceField(
        queryset=Reservation.objects.filter(status=Reservation.STATUS_ACTIVE),
        required=False,
        label="Bestehende Reservierung einlösen (optional)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
