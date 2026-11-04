"""
Automatisierte Unit-Tests für Use Case 3: Medium reservieren
Verantwortlich: Marcel Kitzmantel (3. Autor)

Zu testende kritische Pfade (gemäß Vorgabeblatt & Projektbeschreibung):
- Erfolgreiche Reservierung bei freier Kapazität im zukünftigen Intervall
- Ablehnung bei unzureichender Kapazität (bestehende Ausleihen + Reservierungen >= Gesamtexemplare)
- Ablehnung bei ungültigem Zeitintervall (Vergangenheit oder Start >= Ende)
- Ablehnung bei FSK-Verstoß
- Concurrency-Test: Schutz vor widersprüchlichen Reservierungen / Überbuchung bei parallelen Anfragen
- Automatische Freigabe von Kapazität bei Stornierung oder Fristablauf (Expiration)
- Einhaltung der Best Practices: Test-Isolation, Arrange-Act-Assert (AAA), Boundary/Error Cases
"""

# TODO: Marcel Kitzmantel - Unit-Tests für Use Case 3 hier implementieren
