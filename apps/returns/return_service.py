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
  Überziehungstage ermitteln und Versäumnisgebühr (höchster zutreffender Genre-Tarif)
  auf das Kundenkonto buchen.
- Nutzungsstatistik des Exemplars aktualisieren (Anzahl Ausleihen +1, kumulierte Ausleihdauer erhöht).
- Status des Exemplars auf 'available' setzen, AUSSER der konfigurierte Abnutzungsschwellenwert
  (Usage Threshold) wurde erreicht; dann Status auf 'withdrawn/replacement' setzen.
- Kundenkonto sowie offene Reservierungen für dieses Medium aktualisieren.

Post-Conditions (Fehlerfall):
- Unbekannter Barcode, Medium gehört nicht zur Bibliothek oder kein offener Loan:
  Rückgabestation verweigert physische Annahme, zeigt Fehlerstatus an, keine Serverdaten verändert.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone

from apps.core.models import Copy, Loan, Reservation
from apps.core.policies import RulePolicyEngine
from apps.core.concurrency import ConcurrencyLockManager
from apps.core.repositories import MasterDataRepository, TransactionRepository


class ReturnServiceException(Exception):
    """Basis-Exception für Fehler im Rückgabe-Service."""
    pass


class InvalidBarcodeException(ReturnServiceException):
    """Wird geworfen, wenn der Barcode unbekannt ist oder nicht zur Bibliothek gehört."""
    pass


class NoActiveLoanException(ReturnServiceException):
    """Wird geworfen, wenn für das Exemplar kein aktiver Ausleihvorgang existiert."""
    pass


@dataclass
class ReturnEligibilityResult:
    """Ergebnis der Annahmeprüfung der Rückgabestation."""
    is_eligible: bool
    barcode: str
    media_title: str
    patron_name: str
    patron_number: str
    planned_return_date: datetime
    is_overdue: bool
    overdue_days: int
    estimated_fee: Decimal
    shelf_id: int
    compartment: str
    message: str


@dataclass
class ReturnResult:
    """Ergebnis des abgeschlossenen Rückgabeprozesses."""
    loan: Loan
    copy: Copy
    overdue_days: int
    overdue_fee: Decimal
    is_withdrawn: bool
    has_pending_reservations: bool
    message: str


class IReturnService:
    """Interface für den Rückgabe-Service."""

    def check_return_eligibility(self, barcode: str) -> ReturnEligibilityResult:
        raise NotImplementedError

    def process_return(
        self,
        barcode: str,
        return_timestamp: Optional[datetime] = None
    ) -> ReturnResult:
        raise NotImplementedError


class ReturnService(IReturnService):
    """
    Geschäftslogik für Use Case 2: Medium zurückgeben.
    """

    def check_return_eligibility(self, barcode: str) -> ReturnEligibilityResult:
        """
        Prüft vor der physischen Annahme durch die Station:
        - Gehört das Exemplar zur Bibliothek?
        - Gibt es einen offenen, aktiven Ausleihvorgang?
        - Ermittelt eventuelle Überziehungstage und Gebühren.
        """
        barcode = barcode.strip()
        copy = MasterDataRepository.get_copy_by_barcode(barcode)
        if not copy:
            raise InvalidBarcodeException(
                f"Barcode '{barcode}' unbekannt: Dieses Medium gehört nicht zum Bestand dieser Bibliothek."
            )

        loan = Loan.objects.filter(copy=copy, status=Loan.STATUS_ACTIVE).select_related(
            'patron', 'copy__media', 'copy__location'
        ).first()

        if not loan:
            raise NoActiveLoanException(
                f"Für das Exemplar '{barcode}' ({copy.media.name}) liegt kein offener Ausleihvorgang vor. "
                f"Aktueller Status: {copy.get_status_display()}."
            )

        now = timezone.now()
        overdue_days, estimated_fee = RulePolicyEngine.calculate_overdue_fee(loan, now)
        is_overdue = overdue_days > 0

        msg = f"Exemplar '{copy.media.name}' kann angenommen werden."
        if is_overdue:
            msg += f" ACHTUNG: {overdue_days} Tag(e) überfällig. Versäumnisgebühr: {estimated_fee:.2f} €."

        return ReturnEligibilityResult(
            is_eligible=True,
            barcode=copy.barcode,
            media_title=copy.media.name,
            patron_name=loan.patron.name,
            patron_number=loan.patron.customer_number,
            planned_return_date=loan.planned_return_date,
            is_overdue=is_overdue,
            overdue_days=overdue_days,
            estimated_fee=estimated_fee,
            shelf_id=copy.location.shelf_id,
            compartment=copy.location.compartment,
            message=msg
        )

    def process_return(
        self,
        barcode: str,
        return_timestamp: Optional[datetime] = None
    ) -> ReturnResult:
        """
        Wird nach physischer Annahme des Exemplars ausgeführt:
        - Schließt Loan ab
        - Berechnet Überziehungsgebühren und bucht sie auf das Kundenkonto
        - Aktualisiert Nutzungsstatistiken
        - Führt Abnutzungsschwellenwert-Prüfung durch (Statusübergang)
        - Prüft auf offene Reservierungen
        """
        barcode = barcode.strip()
        if return_timestamp is None:
            return_timestamp = timezone.now()

        with transaction.atomic():
            # 1. Exemplar und Loan unter Concurrency-Sperre laden
            copy = ConcurrencyLockManager.lock_copy_by_barcode(barcode)
            if not copy:
                raise InvalidBarcodeException(f"Unbekannter Barcode: '{barcode}'.")

            loan = ConcurrencyLockManager.lock_loan_for_return(barcode)
            if not loan:
                raise NoActiveLoanException(f"Kein aktiver Ausleihvorgang für Barcode '{barcode}' gefunden.")

            # 2. Überziehungsgebühren berechnen & verbuchen
            overdue_days, fee = RulePolicyEngine.calculate_overdue_fee(loan, return_timestamp)
            if fee > Decimal("0.00"):
                patron = loan.patron
                patron.outstanding_fees += fee
                patron.save(update_fields=['outstanding_fees'])

            # 3. Loan abschließen
            TransactionRepository.close_loan(loan, return_timestamp, fee)

            # 4. Nutzungsdauer und Statistik aktualisieren
            duration_days = max(1, (return_timestamp.date() - loan.checkout_timestamp.date()).days)
            TransactionRepository.update_usage_stats(copy, duration_days)

            # 5. Abnutzungsschwellenwert prüfen (Usage Threshold)
            is_withdrawn = RulePolicyEngine.is_threshold_reached(copy)
            if is_withdrawn:
                copy.status = Copy.STATUS_WITHDRAWN
            else:
                copy.status = Copy.STATUS_AVAILABLE
            copy.save(update_fields=['status'])

            # 6. Offene Reservierungen für das Medium prüfen
            has_pending = Reservation.objects.filter(
                media=copy.media,
                status=Reservation.STATUS_ACTIVE
            ).exists()

            status_text = "Verfügbar (zurückgestellt ins Regal)" if not is_withdrawn else "Ausgesondert (Ersatz erforderlich)"
            msg = (
                f"Rückgabe erfolgreich verbucht! Exemplar: {copy.barcode} ({copy.media.name}). "
                f"Neuer Status: {status_text}."
            )
            if fee > Decimal("0.00"):
                msg += f" Überziehungsgebühr von {fee:.2f} € wurde auf das Konto von {loan.patron.name} gebucht."
            if has_pending:
                msg += " Vormerkung vorhanden: Ein Kunde wartet bereits auf dieses Medium!"

            return ReturnResult(
                loan=loan,
                copy=copy,
                overdue_days=overdue_days,
                overdue_fee=fee,
                is_withdrawn=is_withdrawn,
                has_pending_reservations=has_pending,
                message=msg
            )
