"""
Formulare & Eingabevalidierung für Use Case 2: Medium zurückgeben
Verantwortlich: David Leberbauer (2. Autor)
"""

from django import forms


class BarcodeScanForm(forms.Form):
    """
    Formular für die Barcode-Eingabe an der Rückgabestation.
    """
    barcode = forms.CharField(
        max_length=100,
        label="Barcode des physischen Exemplars",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg font-monospace',
            'placeholder': 'z. B. BARCODE-BOOK-001',
            'autofocus': 'autofocus'
        })
    )
