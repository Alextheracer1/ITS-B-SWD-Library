"""
Domain Rules & Concurrency Layer: Concurrency & Lock Manager
Interface: IConcurrencyLock

Verantwortlich für:
- Schutz vor Doppelzuweisung desselben physischen Exemplars bei gleichzeitigen Ausleihen.
- Schutz vor konkurrierenden Überbuchungen bei gleichzeitigen Reservierungen für dasselbe Medium.
- Synchronisation und Transaktionssicherheit im Multi-User-Betrieb.

Architektur-Referenz: SWD-LiBros.pdf (Kapitel 3.1 Komponentendiagramm)
"""

from datetime import datetime
from typing import Optional, Tuple
from django.db import transaction
from django.utils import timezone
from apps.core.models import Copy, Media, Loan, Reservation


class IConcurrencyLock:
    """Interface für Concurrency- und Transaktionssperren."""

    @staticmethod
    def lock_available_copy(media_id: int) -> Optional[Copy]:
        raise NotImplementedError

    @staticmethod
    def lock_copy_by_barcode(barcode: str) -> Optional[Copy]:
        raise NotImplementedError

    @staticmethod
    def lock_loan_for_return(barcode: str) -> Optional[Loan]:
        raise NotImplementedError

    @staticmethod
    def check_and_lock_reservation_capacity(
        media_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[bool, int, int]:
        raise NotImplementedError


class ConcurrencyLockManager(IConcurrencyLock):
    """
    Verwaltet Transaktionssperren (select_for_update) zur Verhinderung von
    Race Conditions und Doppelbelegungen im Mehrbenutzerbetrieb.
    """

    @classmethod
    def lock_available_copy(cls, media_id: int) -> Optional[Copy]:
        """
        Sucht ein physisches Exemplar (Copy) für das gegebene Medium,
        das den Status 'available' hat, und sperrt es per select_for_update(),
        um Doppelzuweisungen bei gleichzeitigen Anfragen zu verhindern.
        Muss innerhalb einer transaction.atomic() ausgeführt werden.
        """
        copies = Copy.objects.select_for_update().filter(
            media_id=media_id,
            status=Copy.STATUS_AVAILABLE
        ).select_related('location', 'media')

        return copies.first()

    @classmethod
    def lock_copy_by_barcode(cls, barcode: str) -> Optional[Copy]:
        """
        Sperrt ein physisches Exemplar anhand seines Barcodes per select_for_update().
        """
        return Copy.objects.select_for_update().filter(
            barcode=barcode
        ).select_related('media', 'location').first()

    @classmethod
    def lock_loan_for_return(cls, barcode: str) -> Optional[Loan]:
        """
        Sucht und sperrt den aktiven Ausleihvorgang (Loan) für das Exemplar
        mit dem angegebenen Barcode per select_for_update().
        """
        return Loan.objects.select_for_update().filter(
            copy__barcode=barcode,
            status=Loan.STATUS_ACTIVE
        ).select_related('patron', 'copy', 'copy__media', 'copy__location').first()

    @classmethod
    def check_and_lock_reservation_capacity(
        cls,
        media_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[bool, int, int]:
        """
        Prüft die Kapazität eines Mediums für ein Zielzeitintervall
        unter Einsatz von Zeilensperren (select_for_update) auf dem Medium,
        um konkurrierende Überbuchungen zu verhindern.
        
        Gibt (has_capacity, free_slots, total_copies) zurück.
        """
        # Medium mit Sperre laden, um parallele Reservierungsprüfungen zu serialisieren
        media = Media.objects.select_for_update().filter(id=media_id).first()
        if not media:
            return False, 0, 0

        # Gesamtzahl betriebsbereiter Exemplare (nicht ausgesondert)
        total_copies = Copy.objects.filter(
            media_id=media_id
        ).exclude(
            status__in=[Copy.STATUS_WITHDRAWN, Copy.STATUS_MAINTENANCE]
        ).count()

        if total_copies == 0:
            return False, 0, 0

        # Aktive Reservierungen, die das gewünschte Intervall überlappen:
        # [start_date, end_date] überlappt mit [res.start_date, res.end_date] wenn:
        # res.start_date < end_date UND res.end_date > start_date
        overlapping_reservations = Reservation.objects.filter(
            media_id=media_id,
            status=Reservation.STATUS_ACTIVE,
            start_date__lt=end_date,
            end_date__gt=start_date
        ).count()

        # Aktuelle Ausleihen, deren geplante Rückgabe nach dem Startzeitpunkt liegt
        overlapping_loans = Loan.objects.filter(
            copy__media_id=media_id,
            status=Loan.STATUS_ACTIVE,
            planned_return_date__gt=start_date
        ).count()

        occupied_slots = overlapping_reservations + overlapping_loans
        free_slots = total_copies - occupied_slots

        has_capacity = free_slots > 0
        return has_capacity, max(0, free_slots), total_copies
