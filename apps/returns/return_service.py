"""
Use Case 2: Medium zurückgeben (Return)
Service Layer: IReturnService
Verantwortlich: David Leberbauer (2. Autor)

Spezifikation laut SWD-Projekt-Library.pdf (Abschnitt 4.2) & SWD-LiBros.pdf (Abschnitt 2.3):
-----------------------------------------------------------------------------------------
Trigger:
- Ein Kunde scannt den eindeutigen Barcode eines physischen Exemplars (Copy) an einer
  automatisierten Rückgabestation (Return Station). Die Station sendet eine Annahmeanfrage
  an den zentralen Server.

Pre-Conditions (Vorbedingungen):
- Rückgabestation (bzw. HTML-Simulationsinterface) ist aktiv und mit zentralem Server verbunden.
- Gescannter Barcode gehört zu einem physischen Exemplar dieser Bibliothek.
- Für dieses Exemplar existiert ein aktiver, noch offener Ausleihvorgang (Loan).

Post-Conditions (Erfolgsfall):
- Rückgabestation nimmt Exemplar physisch an und meldet Erfolg an den Server.
- Actual Return Timestamp wird erfasst und der Loan als abgeschlossen ('closed') markiert.
- Bei Fristüberschreitung (Actual Return > Planned Return Date):
  Überziehungstage ermitteln und Versäumnisgebühr (abhängig von Medientyp und höchstem Genre-Tarif)
  auf das Kundenkonto buchen.
- Nutzungsstatistik des Exemplars aktualisieren (Anzahl Ausleihen +1, kumulierte Ausleihdauer erhöht).
- Status des Exemplars auf 'available' setzen, AUSSER der konfigurierte Abnutzungsschwellenwert
  (Usage Threshold) wurde erreicht oder Wartung steht an; dann Status auf 'withdrawn/replacement' setzen.
- Kundenkonto sowie offene Reservierungen für dieses Medium aktualisieren.

Post-Conditions (Fehlerfall):
- Unbekannter Barcode, Medium gehört nicht zur Bibliothek oder kein offener Loan:
  Rückgabestation verweigert physische Annahme, zeigt Fehlerstatus an, keine Serverdaten verändert.
"""

# TODO: David Leberbauer - Hier die Geschäftslogik für den Return Service implementieren
