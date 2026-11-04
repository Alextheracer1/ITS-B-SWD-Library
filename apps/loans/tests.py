"""
Automatisierte Unit-Tests für Use Case 1: Medium ausleihen
Verantwortlich: Alexander Graf (1. Autor)

Zu testende kritische Pfade (gemäß Vorgabeblatt & Projektbeschreibung):
- Erfolgreiche Ausleihe bei verfügbarem Exemplar
- Ablehnung bei FSK-Verstoß (z. B. Jugendlicher versucht FSK-18 DVD zu leihen)
- Ablehnung bei fehlender Verfügbarkeit
- Erfolgreiche Ausleihe mit vorheriger Reservierung
- Berechnung der Leihfrist (4 Wochen Standard vs. 6 Wochen für Studenten bei Fachbüchern)
- Concurrency-Test: Schutz vor Doppelzuweisung des letzten Exemplars bei zeitgleicher Anfrage
- Einhaltung der Best Practices: Test-Isolation, Arrange-Act-Assert (AAA), Boundary/Error Cases
"""

# TODO: Alexander Graf - Unit-Tests für Use Case 1 hier implementieren
