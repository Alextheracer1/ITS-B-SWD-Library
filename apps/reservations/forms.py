"""
Formulare & Eingabevalidierung für Use Case 3: Medium reservieren
Verantwortlich: Marcel Kitzmantel (3. Autor)
"""

from datetime import timedelta
from django import forms
from django.utils import timezone
from apps.core.models import Patron, Media


class ReservationForm(forms.Form):
    """
    Formular zur Reservierung eines Mediums für ein zukünftiges Zeitintervall.
    """
    patron = forms.ModelChoiceField(
        queryset=Patron.objects.all(),
        label="Kunde (Patron)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    media = forms.ModelChoiceField(
        queryset=Media.objects.all(),
        label="Medium (Titel)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        label="Reservierungs-Start",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'min': timezone.localdate().isoformat()
        }),
        initial=timezone.localdate
    )
    end_date = forms.DateField(
        label="Reservierungs-Ende",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'min': (timezone.localdate() + timedelta(days=1)).isoformat()
        }),
        initial=lambda: timezone.localdate() + timedelta(days=14)
    )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        if start and end:
            if start < timezone.localdate():
                self.add_error('start_date', "Das Startdatum darf nicht in der Vergangenheit liegen.")
            if end <= start:
                self.add_error('end_date', "Das Enddatum muss nach dem Startdatum liegen.")

        return cleaned_data
