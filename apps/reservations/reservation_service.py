"""
Use Case 3: Medium reservieren (Reservation)
Service Layer: IReservationService
Verantwortlich: Marcel Kitzmantel (3. Autor)

Spezifikation laut SWD-Projekt-Library.pdf (Abschnitt 4.3) & SWD-LiBros.pdf (Abschnitt 2.4):
-----------------------------------------------------------------------------------------
Trigger:
- Ein Kunde wählt in der Web-Applikation ein Medium (auf Titelebene) sowie ein zukünftiges
  Zeitintervall aus und sendet eine Reservierungsanfrage ab.

Pre-Conditions (Vorbedingungen):
- Kunde ist registriert, authentifiziert (Geburtsdatum im Kundenstamm).
- Gewähltes Medium existiert im System und das angefragte Zeitintervall liegt gültig in der Zukunft.
- Kunde erfüllt erforderliche Altersfreigabe (FSK) für das gewählte Medium.
- Im gewünschten Zielintervall ist mindestens ein Exemplar des Mediums rechnerisch frei
  (Gesamtzahl verfügbarer Exemplare > bestehende Ausleihen + Reservierungen in diesem Zeitraum).

Post-Conditions (Erfolgsfall):
- Unter Concurrency Control (Schutz vor überlappenden Parallelbuchungen) wird ein neuer
  Reservation-Datensatz für das Medium (Titelebene) angelegt.
- Speichert Reservation Timestamp sowie Last Pickup Date (Abholfrist).
- Verfügbare Reservierungskapazität des Mediums für das Zeitintervall ist um 1 reduziert.
- Kunde erhält Reservierungsbestätigung.

Lifecycle bis zum Last Pickup Date:
- Holt der Kunde das Medium fristgerecht ab -> Übergang in UC-01 (Loan), Reservierung im Loan referenziert.
- Storniert der Kunde vorab -> Reservierung aufgehoben, Kapazität wieder frei.
- Verstreicht Last Pickup Date ohne Abholung -> Reservierung läuft automatisch ab (expired), Kapazität wieder frei.

Post-Conditions (Fehlerfall):
- Bei FSK-Ablehnung, fehlender Kapazität im Zielintervall oder Concurrency-Konflikt:
  Keine Reservierung gespeichert, Fehler an Kunden gemeldet.
"""

# TODO: Marcel Kitzmantel - Hier die Geschäftslogik für den Reservation Service implementieren
