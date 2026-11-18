"""
Data Access / Persistence Layer: Repositories
Interfaces: IMasterDataAccess, ITransactionAccess

Verantwortlich für:
- Master Data Repository: Gekapselter Zugriff auf Media, Copy, Location, Patron
- Transaction Repository: Gekapselter Zugriff auf Loan, Reservation, UsageStats

Architektur-Referenz: SWD-LiBros.pdf (Kapitel 3.1 Komponentendiagramm)
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from django.db.models import Q
from apps.core.models import (
    Media, Copy, Location, Patron,
    Loan, Reservation, UsageStats
)


class IMasterDataAccess:
    """Interface für gekapselten Zugriff auf Stammdaten."""

    @staticmethod
    def get_media_by_id(media_id: int) -> Optional[Media]:
        raise NotImplementedError

    @staticmethod
    def get_patron_by_id(patron_id: int) -> Optional[Patron]:
        raise NotImplementedError

    @staticmethod
    def get_copy_by_barcode(barcode: str) -> Optional[Copy]:
        raise NotImplementedError

    @staticmethod
    def get_available_copies_count(media_id: int) -> int:
        raise NotImplementedError


class ITransactionAccess:
    """Interface für gekapselten Zugriff auf Transaktionsdaten."""

    @staticmethod
    def create_loan(
        patron: Patron,
        copy: Copy,
        planned_return_date: datetime,
        reservation: Optional[Reservation] = None
    ) -> Loan:
        raise NotImplementedError

    @staticmethod
    def close_loan(
        loan: Loan,
        return_timestamp: datetime,
        overdue_fee: Decimal
    ) -> Loan:
        raise NotImplementedError

    @staticmethod
    def create_reservation(
        patron: Patron,
        media: Media,
        start_date: datetime,
        end_date: datetime,
        last_pickup_date: datetime
    ) -> Reservation:
        raise NotImplementedError

    @staticmethod
    def update_usage_stats(copy: Copy, duration_days: int) -> UsageStats:
        raise NotImplementedError


class MasterDataRepository(IMasterDataAccess):
    """Repository für alle Abfragen von Stammdaten (Media, Copy, Location, Patron)."""

    @classmethod
    def get_media_by_id(cls, media_id: int) -> Optional[Media]:
        return Media.objects.filter(id=media_id).prefetch_related('genres', 'copies').first()

    @classmethod
    def get_patron_by_id(cls, patron_id: int) -> Optional[Patron]:
        return Patron.objects.filter(id=patron_id).first()

    @classmethod
    def get_patron_by_number(cls, customer_number: str) -> Optional[Patron]:
        return Patron.objects.filter(customer_number=customer_number).first()

    @classmethod
    def get_copy_by_barcode(cls, barcode: str) -> Optional[Copy]:
        return Copy.objects.filter(barcode=barcode).select_related('media', 'location').first()

    @classmethod
    def get_available_copies_count(cls, media_id: int) -> int:
        return Copy.objects.filter(media_id=media_id, status=Copy.STATUS_AVAILABLE).count()

    @classmethod
    def list_all_media(cls, search_query: Optional[str] = None) -> List[Media]:
        qs = Media.objects.all().prefetch_related('genres', 'copies', 'copies__location')
        if search_query:
            qs = qs.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        return list(qs)


class TransactionRepository(ITransactionAccess):
    """Repository für alle transaktionalen Schreib- und Lesezugriffe (Loan, Reservation, UsageStats)."""

    @classmethod
    def create_loan(
        cls,
        patron: Patron,
        copy: Copy,
        planned_return_date: datetime,
        reservation: Optional[Reservation] = None
    ) -> Loan:
        loan = Loan.objects.create(
            patron=patron,
            copy=copy,
            planned_return_date=planned_return_date,
            reservation=reservation,
            status=Loan.STATUS_ACTIVE
        )
        # Status des physischen Exemplars auf 'on_loan' aktualisieren
        copy.status = Copy.STATUS_ON_LOAN
        copy.save(update_fields=['status'])
        return loan

    @classmethod
    def close_loan(
        cls,
        loan: Loan,
        return_timestamp: datetime,
        overdue_fee: Decimal
    ) -> Loan:
        loan.actual_return_timestamp = return_timestamp
        loan.overdue_fee = overdue_fee
        loan.status = Loan.STATUS_CLOSED
        loan.save(update_fields=['actual_return_timestamp', 'overdue_fee', 'status'])
        return loan

    @classmethod
    def create_reservation(
        cls,
        patron: Patron,
        media: Media,
        start_date: datetime,
        end_date: datetime,
        last_pickup_date: datetime
    ) -> Reservation:
        return Reservation.objects.create(
            patron=patron,
            media=media,
            start_date=start_date,
            end_date=end_date,
            last_pickup_date=last_pickup_date,
            status=Reservation.STATUS_ACTIVE
        )

    @classmethod
    def update_usage_stats(cls, copy: Copy, duration_days: int) -> UsageStats:
        """
        Aktualisiert Nutzungsstatistik des Exemplars (total_loans + 1, cumulative_duration += duration_days).
        """
        stats, _ = UsageStats.objects.get_or_create(
            copy=copy,
            defaults={'total_loans': 0, 'cumulative_duration': 0}
        )
        stats.total_loans += 1
        stats.cumulative_duration += max(1, duration_days)
        stats.save()

        # Auch den Zähler auf dem Copy-Objekt synchronisieren
        copy.usage_count += 1
        copy.save(update_fields=['usage_count'])
        return stats
