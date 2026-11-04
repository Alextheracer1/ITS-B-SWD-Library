"""
Automatisierte Unit-Tests für Use Case 2: Medium zurückgeben
Verantwortlich: David Leberbauer (2. Autor)

Zu testende kritische Pfade (gemäß Vorgabeblatt & Projektbeschreibung):
- Erfolgreiche Rückgabe eines fristgerecht ausgeliehenen Exemplars
- Rückgabe mit Fristüberschreitung: Korrekte Berechnung der Versäumnisgebühren (höchster Genre-Tarif)
  und Buchung auf Kundenkonto
- Korrekte Aktualisierung der Nutzungsstatistik (total_loans +1, cumulative_duration)
- Erreichen des Abnutzungsschwellenwerts (Usage Threshold): Statusübergang auf 'withdrawn/replacement'
- Ablehnung bei unbekanntem Barcode oder nicht ausgeliehenem Exemplar (keine Datenänderung)
- Einhaltung der Best Practices: Test-Isolation, Arrange-Act-Assert (AAA), Boundary/Error Cases
"""

# TODO: David Leberbauer - Unit-Tests für Use Case 2 hier implementieren
