"""
Use Case 1: Medium ausleihen (Loan)
Service Layer: ILoanService
Verantwortlich: Alexander Graf (1. Autor)

Spezifikation laut SWD-Projekt-Library.pdf (Abschnitt 4.1) & SWD-LiBros.pdf (Abschnitt 2.2):
-----------------------------------------------------------------------------------------
Trigger:
- Ein Kunde wählt in der Web-Applikation oder am Kiosk-Terminal ein Medium (Titelebene) aus
  und fordert die Ausleihe an bzw. bestätigt diese.

Pre-Conditions (Vorbedingungen):
- Kunde ist registriert, authentifiziert (Geburtsdatum und Kundentyp hinterlegt).
- Medium existiert in den Stammdaten.
- Altersfreigabe (FSK) des Mediums wird anhand des Kundengeburtsdatums erfüllt.
- Mindestens ein physisches Exemplar (Copy) ist für den Zeitraum verfügbar (weder ausgeliehen
  noch anderweitig reserviert), ODER es liegt eine gültige Reservierung genau dieses Kunden vor.

Post-Conditions (Erfolgsfall):
- Ein konkretes physisches Exemplar (Copy) wird unter Transaktionssperre (Concurrency Control,
  select_for_update) eindeutig zugewiesen und Status auf 'ausgeliehen' gesetzt.
- Neuer Loan-Datensatz mit Checkout-Timestamp und berechnetem Planned Return Date angelegt
  (Standard: 4 Wochen; Studenten bei Fachbüchern: bis zu 6 Wochen).
- Falls vorher reserviert: Reservierung im Loan referenzieren und als eingelöst/erfüllt markieren.
- Anzeige von Ausleihbestätigung und physischem Standort (Shelf-ID und Compartment).

Post-Conditions (Fehlerfall):
- Bei FSK-Verstoß, fehlender Verfügbarkeit oder Concurrency-Konflikt: Kein Loan, Status unverändert, Fehlermeldung.
"""

# TODO: Alexander Graf - Hier die Geschäftslogik für den Loan Service implementieren
