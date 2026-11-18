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
  select_for_update) eindeutig zugewiesen und Status auf 'on_loan' gesetzt.
- Neuer Loan-Datensatz mit Checkout-Timestamp und berechnetem Planned Return Date angelegt
  (Standard: 4 Wochen; Studenten bei Fachbüchern: bis zu 6 Wochen).
- Falls vorher reserviert: Reservierung im Loan referenzieren und als eingelöst/erfüllt markieren.
- Anzeige von Ausleihbestätigung und physischem Standort (Shelf-ID und Compartment).

Post-Conditions (Fehlerfall):
- Bei FSK-Verstoß, fehlender Verfügbarkeit oder Concurrency-Konflikt: Kein Loan, Status unverändert, Fehlermeldung.
"""

from dataclasses import dataclass
from typing import Optional
from django.db import transaction, OperationalError
from django.utils import timezone

from apps.core.models import Patron, Media, Copy, Loan, Reservation
from apps.core.policies import RulePolicyEngine
from apps.core.concurrency import ConcurrencyLockManager
from apps.core.repositories import MasterDataRepository, TransactionRepository


class LoanServiceException(Exception):
    """Basis-Exception für Fehler im Ausleih-Service."""
    pass


class FSKViolationException(LoanServiceException):
    """Wird geworfen, wenn das Kundenalter für das Medium nicht ausreicht."""
    pass


class UnavailableMediaException(LoanServiceException):
    """Wird geworfen, wenn kein physisches Exemplar frei ist."""
    pass


@dataclass
class LoanResult:
    """Ergebnisobjekt eines erfolgreichen Ausleihvorgangs."""
    loan: Loan
    copy: Copy
    shelf_id: int
    compartment: str
    message: str


class ILoanService:
    """Interface für den Ausleih-Service."""

    def borrow_media(
        self,
        patron_id: int,
        media_id: int,
        reservation_id: Optional[int] = None
    ) -> LoanResult:
        raise NotImplementedError


class LoanService(ILoanService):
    """
    Geschäftslogik für Use Case 1: Medium ausleihen.
    """

    def borrow_media(
        self,
        patron_id: int,
        media_id: int,
        reservation_id: Optional[int] = None
    ) -> LoanResult:
        # 1. Patron & Media aus MasterDataRepository laden
        patron = MasterDataRepository.get_patron_by_id(patron_id)
        if not patron:
            raise LoanServiceException(f"Kunde mit ID {patron_id} wurde nicht gefunden.")

        media = MasterDataRepository.get_media_by_id(media_id)
        if not media:
            raise LoanServiceException(f"Medium mit ID {media_id} wurde nicht gefunden.")

        # 2. FSK / Altersfreigabe prüfen
        is_allowed, fsk_reason = RulePolicyEngine.validate_age(patron, media)
        if not is_allowed:
            raise FSKViolationException(fsk_reason)

        # 3. Leihfrist berechnen (Standard 4 Wochen, Studenten bei Fachbüchern 6 Wochen)
        planned_return_date = RulePolicyEngine.calculate_planned_return_date(patron, media)

        # 4. Concurrency Control & Exemplar-Zuweisung innerhalb einer atomaren Transaktion
        try:
            with transaction.atomic():
                # Prüfen, ob eine gültige Reservierung vorliegt
                reservation: Optional[Reservation] = None
                if reservation_id:
                    try:
                        reservation = Reservation.objects.select_for_update().get(
                            id=reservation_id,
                            patron=patron,
                            media=media,
                            status=Reservation.STATUS_ACTIVE
                        )
                    except Reservation.DoesNotExist:
                        raise LoanServiceException("Die angegebene Reservierung ist ungültig oder gehört nicht zu diesem Kunden/Medium.")
                else:
                    # Automatisch prüfen, ob eine aktive Reservierung für diesen Patron & Media existiert
                    reservation = Reservation.objects.select_for_update().filter(
                        patron=patron,
                        media=media,
                        status=Reservation.STATUS_ACTIVE
                    ).first()

                # Physisches Exemplar mit Sperre (select_for_update) finden
                copy = ConcurrencyLockManager.lock_available_copy(media_id)
                if not copy:
                    raise UnavailableMediaException(
                        f"Derzeit ist kein freies Exemplar des Titels '{media.name}' verfügbar."
                    )

                # Loan-Datensatz erstellen und Exemplarstatus auf 'on_loan' setzen
                loan = TransactionRepository.create_loan(
                    patron=patron,
                    copy=copy,
                    planned_return_date=planned_return_date,
                    reservation=reservation
                )

                # Falls Reservierung vorausging: als erfüllt/eingelöst markieren
                if reservation:
                    reservation.status = Reservation.STATUS_FULFILLED
                    reservation.save(update_fields=['status'])

                location = copy.location

                return LoanResult(
                    loan=loan,
                    copy=copy,
                    shelf_id=location.shelf_id,
                    compartment=location.compartment,
                    message=(
                        f"Ausleihe erfolgreich! Exemplar '{copy.barcode}' entnommen. "
                        f"Standort: Regal {location.shelf_id}, Fach {location.compartment}. "
                        f"Fälligkeitsdatum: {planned_return_date.strftime('%d.%m.%Y')}."
                    )
                )
        except OperationalError:
            raise UnavailableMediaException(
                f"Kollision bei gleichzeitiger Ausleihe für '{media.name}'. "
                "Doppelzuweisung wurde durch Transaktionssperre verhindert."
            )
