"""
Domain Rules & Concurrency Layer: Rule & Policy Engine
Interfaces: IPolicyValidation, IFeeAndThreshold

Verantwortlich für:
- FSK / Altersfreigabe-Validierung anhand des Patron-Geburtsdatums
- Leihfristen-Berechnung (Standard: 4 Wochen, Studenten bei Fachbüchern: bis zu 6 Wochen)
- Versäumnisgebühren-Berechnung (abhängig von Medientyp und höchstem Genre-Tarif)
- Abnutzungsschwellenwert-Prüfung (Usage Threshold für Aussonderung/Ersatz)

Architektur-Referenz: SWD-LiBros.pdf (Kapitel 3.1 Komponentendiagramm)
"""

# Hier können Geschäftsregeln und Berechnungsfunktionen zentral definiert werden.
