"""
Domain Rules & Concurrency Layer: Concurrency & Lock Manager
Interface: IConcurrencyLock

Verantwortlich für:
- Schutz vor Doppelzuweisung desselben physischen Exemplars bei gleichzeitigen Ausleihen.
- Schutz vor konkurrierenden Überbuchungen bei gleichzeitigen Reservierungen für dasselbe Medium.
- Synchronisation und Transaktionssicherheit im Multi-User-Betrieb.

Architektur-Referenz: SWD-LiBros.pdf (Kapitel 3.1 Komponentendiagramm)
"""

# Hier können Hilfsklassen/Dekoratoren für Datenbanktransaktionen (z.B. select_for_update)
# oder Lock-Mechanismen definiert werden.
