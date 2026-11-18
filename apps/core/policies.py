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

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple
from django.utils import timezone
from apps.core.models import Patron, Media, Specialized_Book, Loan, Copy


class IPolicyValidation:
    """Interface für FSK- und Leihfrist-Validierungen."""

    @staticmethod
    def validate_age(patron: Patron, media: Media) -> Tuple[bool, str]:
        raise NotImplementedError

    @staticmethod
    def calculate_planned_return_date(
        patron: Patron,
        media: Media,
        start_time: Optional[datetime] = None
    ) -> datetime:
        raise NotImplementedError


class IFeeAndThreshold:
    """Interface für Gebühren- und Schwellenwert-Berechnungen."""

    @staticmethod
    def calculate_overdue_fee(
        loan: Loan,
        return_timestamp: Optional[datetime] = None
    ) -> Tuple[int, Decimal]:
        raise NotImplementedError

    @staticmethod
    def is_threshold_reached(copy: Copy, threshold: int = 50) -> bool:
        raise NotImplementedError


class RulePolicyEngine(IPolicyValidation, IFeeAndThreshold):
    """
    Zentrale Implementierung aller Geschäftsregeln des Bibliothekssystems.
    """

    # Konfigurierbarer Standard-Schwellenwert für Abnutzung (Usage Threshold)
    DEFAULT_USAGE_THRESHOLD = 50

    # Standard-Leihfristen in Tagen
    STANDARD_LOAN_DAYS = 28       # 4 Wochen
    STUDENT_SPECIALIZED_LOAN_DAYS = 42  # 6 Wochen für Studierende bei Fachbüchern

    @classmethod
    def validate_age(cls, patron: Patron, media: Media) -> Tuple[bool, str]:
        """
        Prüft die Altersfreigabe (FSK) des Kunden für das ausgewählte Medium.
        Gibt (True, "") zurück wenn erlaubt, sonst (False, Fehlermeldung).
        """
        age = patron.calculate_age()

        # FSK-Prüfung
        if media.age_limit > 0 and age < media.age_limit:
            return (
                False,
                f"Ausleihe verweigert: Kunde ist {age} Jahre alt, das Medium erfordert jedoch ein Mindestalter von {media.age_limit} Jahren (FSK {media.age_limit})."
            )

        # Zusätzliche Prüfung: Jugendliche dürfen keine FSK-18 Medien / Movies for Adults ausleihen
        if patron.customer_type == Patron.CUSTOMER_TYPE_YOUTH and media.age_limit >= 18:
            return (
                False,
                "Ausleihe verweigert: Jugendliche Kunden dürfen keine Medien für Erwachsene (FSK 18) ausleihen."
            )

        return (True, "Altersfreigabe erfüllt.")

    @classmethod
    def calculate_planned_return_date(
        cls,
        patron: Patron,
        media: Media,
        start_time: Optional[datetime] = None
    ) -> datetime:
        """
        Berechnet das geplante Rückgabedatum.
        - Standard: 4 Wochen (28 Tage)
        - Studenten bei Fachbüchern (Specialized_Book): bis zu 6 Wochen (42 Tage)
        """
        if start_time is None:
            start_time = timezone.now()

        # Prüfen ob Medium ein Fachbuch ist und Patron Student ist
        is_specialized_book = (
            isinstance(media, Specialized_Book) or
            Specialized_Book.objects.filter(id=media.id).exists()
        )
        if patron.customer_type == Patron.CUSTOMER_TYPE_STUDENT and is_specialized_book:
            return start_time + timedelta(days=cls.STUDENT_SPECIALIZED_LOAN_DAYS)

        return start_time + timedelta(days=cls.STANDARD_LOAN_DAYS)

    @classmethod
    def calculate_overdue_fee(
        cls,
        loan: Loan,
        return_timestamp: Optional[datetime] = None
    ) -> Tuple[int, Decimal]:
        """
        Ermittelt bei Überschreitung des Rückgabedatums die Überziehungstage
        und die fällige Versäumnisgebühr.
        Gebührensatz: Höchster Tarif aller zugeordneten Genres des Mediums.
        Gibt (overdue_days, fee_amount) zurück.
        """
        if return_timestamp is None:
            return_timestamp = timezone.now()

        # Vergleich auf Datumsebene (Tage)
        planned_date = loan.planned_return_date.date()
        return_date = return_timestamp.date()

        if return_date <= planned_date:
            return 0, Decimal("0.00")

        overdue_days = (return_date - planned_date).days

        # Höchsten Tagessatz aller Genres des Mediums ermitteln
        media = loan.copy.media
        genres = list(media.genres.all())
        if genres:
            highest_daily_fee = max(g.daily_overdue_fee for g in genres)
        else:
            highest_daily_fee = Decimal("0.50")

        total_fee = Decimal(overdue_days) * highest_daily_fee
        return overdue_days, total_fee.quantize(Decimal("0.01"))

    @classmethod
    def is_threshold_reached(cls, copy: Copy, threshold: Optional[int] = None) -> bool:
        """
        Prüft, ob der Abnutzungsschwellenwert für ein physisches Exemplar erreicht wurde.
        """
        limit = threshold if threshold is not None else cls.DEFAULT_USAGE_THRESHOLD
        
        # Prüfung über Copy.usage_count oder UsageStats falls vorhanden
        usage = copy.usage_count
        if hasattr(copy, 'usage_stats'):
            usage = max(usage, copy.usage_stats.total_loans)

        return usage >= limit
