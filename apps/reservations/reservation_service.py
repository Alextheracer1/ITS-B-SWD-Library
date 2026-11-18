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

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List
from django.db import transaction, OperationalError
from django.utils import timezone

from apps.core.models import Patron, Media, Reservation
from apps.core.policies import RulePolicyEngine
from apps.core.concurrency import ConcurrencyLockManager
from apps.core.repositories import MasterDataRepository, TransactionRepository


class ReservationServiceException(Exception):
    """Basis-Exception für Fehler im Reservierungs-Service."""
    pass


class InvalidIntervalException(ReservationServiceException):
    """Wird geworfen, wenn das Zeitintervall unlogisch ist oder in der Vergangenheit liegt."""
    pass


class ReservationFSKViolationException(ReservationServiceException):
    """Wird geworfen, wenn das Kundenalter für das Medium nicht ausreicht."""
    pass


class CapacityExceededException(ReservationServiceException):
    """Wird geworfen, wenn im Zielzeitraum alle Exemplare belegt oder reserviert sind."""
    pass


@dataclass
class ReservationResult:
    """Ergebnis einer erfolgreichen Reservierung."""
    reservation: Reservation
    last_pickup_date: datetime
    available_capacity_remaining: int
    message: str


class IReservationService:
    """Interface für den Reservierungs-Service."""

    def create_reservation(
        self,
        patron_id: int,
        media_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> ReservationResult:
        raise NotImplementedError

    def cancel_reservation(
        self,
        reservation_id: int,
        patron_id: Optional[int] = None
    ) -> Reservation:
        raise NotImplementedError

    def expire_outdated_reservations(self) -> int:
        raise NotImplementedError


class ReservationService(IReservationService):
    """
    Geschäftslogik für Use Case 3: Medium reservieren.
    """

    # Konfigurierbares Abholzeitfenster ab Beginn des Reservierungsintervalls
    DEFAULT_PICKUP_WINDOW_DAYS = 3

    def create_reservation(
        self,
        patron_id: int,
        media_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> ReservationResult:
        now = timezone.now()

        # 1. Intervall-Validierung
        if start_date >= end_date:
            raise InvalidIntervalException("Das Startdatum muss vor dem Enddatum liegen.")

        if end_date <= now:
            raise InvalidIntervalException("Das gewünschte Reservierungsintervall darf nicht in der Vergangenheit liegen.")

        # 2. Stammdaten laden
        patron = MasterDataRepository.get_patron_by_id(patron_id)
        if not patron:
            raise ReservationServiceException(f"Kunde mit ID {patron_id} existiert nicht.")

        media = MasterDataRepository.get_media_by_id(media_id)
        if not media:
            raise ReservationServiceException(f"Medium mit ID {media_id} existiert nicht.")

        # 3. FSK / Altersfreigabe prüfen
        is_allowed, fsk_reason = RulePolicyEngine.validate_age(patron, media)
        if not is_allowed:
            raise ReservationFSKViolationException(fsk_reason)

        # 4. Concurrency Control & Kapazitätsprüfung innerhalb einer Transaktion
        try:
            # Vorab abgelaufene Reservierungen bereinigen
            self.expire_outdated_reservations()

            with transaction.atomic():
                has_capacity, free_slots, total_copies = ConcurrencyLockManager.check_and_lock_reservation_capacity(
                    media_id=media_id,
                    start_date=start_date,
                    end_date=end_date
                )

                if not has_capacity:
                    raise CapacityExceededException(
                        f"Für den Titel '{media.name}' besteht im gewählten Zeitraum keine freie Kapazität "
                        f"(Gesamtexemplare: {total_copies}, alle durch bestehende Ausleihen oder Reservierungen belegt)."
                    )

                # Abholfrist (Last Pickup Date) berechnen
                last_pickup_date = min(
                    start_date + timedelta(days=self.DEFAULT_PICKUP_WINDOW_DAYS),
                    end_date
                )

                # Reservierungs-Datensatz anlegen
                reservation = TransactionRepository.create_reservation(
                    patron=patron,
                    media=media,
                    start_date=start_date,
                    end_date=end_date,
                    last_pickup_date=last_pickup_date
                )

                remaining_slots = free_slots - 1
                msg = (
                    f"Reservierung erfolgreich angelegt! Titel: '{media.name}' für {patron.name}. "
                    f"Gültig von {start_date.strftime('%d.%m.%Y')} bis {end_date.strftime('%d.%m.%Y')}. "
                    f"Abholfrist (Last Pickup Date): {last_pickup_date.strftime('%d.%m.%Y')}."
                )

                return ReservationResult(
                    reservation=reservation,
                    last_pickup_date=last_pickup_date,
                    available_capacity_remaining=remaining_slots,
                    message=msg
                )
        except OperationalError:
            # Bei SQLite / DBMS-Sperrkollisionen während gleichzeitiger Schreibvorgänge
            raise CapacityExceededException(
                f"Kollision bei gleichzeitiger Reservierungsanfrage für '{media.name}'. "
                "Überbuchung wurde durch Transaktionssperre verhindert. Bitte erneut versuchen."
            )

    def cancel_reservation(
        self,
        reservation_id: int,
        patron_id: Optional[int] = None
    ) -> Reservation:
        """
        Storniert eine aktive Reservierung und gibt die Kapazität sofort wieder frei.
        """
        with transaction.atomic():
            qs = Reservation.objects.select_for_update().filter(id=reservation_id)
            if patron_id is not None:
                qs = qs.filter(patron_id=patron_id)

            reservation = qs.first()
            if not reservation:
                raise ReservationServiceException("Reservierung nicht gefunden oder keine Berechtigung.")

            if reservation.status != Reservation.STATUS_ACTIVE:
                raise ReservationServiceException(
                    f"Reservierung kann nicht storniert werden, da ihr aktueller Status '{reservation.get_status_display()}' ist."
                )

            reservation.status = Reservation.STATUS_CANCELLED
            reservation.save(update_fields=['status'])
            return reservation

    def expire_outdated_reservations(self) -> int:
        """
        Prüft verfallene Reservierungen (now > last_pickup_date) und setzt sie auf 'expired'.
        Gibt die Anzahl der abgelaufenen Reservierungen zurück.
        """
        now = timezone.now()
        try:
            count = Reservation.objects.filter(
                status=Reservation.STATUS_ACTIVE,
                last_pickup_date__lt=now
            ).update(status=Reservation.STATUS_EXPIRED)
            return count
        except OperationalError:
            return 0

    def list_active_reservations(self, patron_id: Optional[int] = None) -> List[Reservation]:
        """Liefert aktive Reservierungen sortiert nach Abholfrist."""
        self.expire_outdated_reservations()
        qs = Reservation.objects.filter(status=Reservation.STATUS_ACTIVE).select_related('patron', 'media')
        if patron_id:
            qs = qs.filter(patron_id=patron_id)
        return list(qs.order_by('last_pickup_date'))
