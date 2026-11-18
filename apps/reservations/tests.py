"""
Automatisierte Unit-Tests für Use Case 3: Medium reservieren
Verantwortlich: Marcel Kitzmantel (3. Autor)

Zu testende kritische Pfade (gemäß Vorgabeblatt & Projektbeschreibung):
- Erfolgreiche Reservierung bei freier Kapazität im zukünftigen Intervall
- Ablehnung bei unzureichender Kapazität (bestehende Ausleihen + Reservierungen >= Gesamtexemplare)
- Ablehnung bei ungültigem Zeitintervall (Vergangenheit oder Start >= Ende)
- Ablehnung bei FSK-Verstoß
- Concurrency-Test: Schutz vor widersprüchlichen Reservierungen / Überbuchung bei parallelen Anfragen
- Automatische Freigabe von Kapazität bei Stornierung oder Fristablauf (Expiration)
- Einhaltung der Best Practices: Test-Isolation, Arrange-Act-Assert (AAA), Boundary/Error Cases
"""

from datetime import date, timedelta
from decimal import Decimal
import threading
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    Genre, Location, Patron, Simple_Book, DVD, Copy, Reservation, Loan
)
from apps.reservations.reservation_service import (
    ReservationService,
    InvalidIntervalException,
    ReservationFSKViolationException,
    CapacityExceededException
)


class ReservationServiceTests(TestCase):
    """
    Test-Suite für die Kernlogik des ReservationService (Use Case 3).
    """

    def setUp(self):
        self.service = ReservationService()
        self.location = Location.objects.create(shelf_id=4, compartment="Fach-4D")

        self.genre_roman = Genre.objects.create(name="Belletristik", daily_overdue_fee=Decimal("0.50"))
        self.genre_fsk18 = Genre.objects.create(name="FSK 18 Action", daily_overdue_fee=Decimal("1.50"))

        self.adult = Patron.objects.create(
            customer_number="CUST-RES-01",
            name="Anna Reserviererin",
            birthday=date(1993, 6, 14),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="anna@res.at"
        )
        self.youth = Patron.objects.create(
            customer_number="CUST-RES-02",
            name="Jonas Teenager",
            birthday=timezone.localdate() - timedelta(days=13 * 365),
            customer_type=Patron.CUSTOMER_TYPE_YOUTH,
            email="jonas@res.at"
        )

        self.book = Simple_Book.objects.create(
            name="Der reservierte Bestseller",
            isbn="777-666-555",
            author="Star Autor",
            age_limit=0
        )
        self.book.genres.add(self.genre_roman)

        self.dvd18 = DVD.objects.create(
            name="Erwachsenenfilm FSK 18",
            director="Director Cut",
            runtime=120,
            age_limit=18
        )
        self.dvd18.genres.add(self.genre_fsk18)

        # 1 physisches Exemplar für das Buch
        self.copy = Copy.objects.create(
            barcode="BC-RES-BOOK-01",
            media=self.book,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )

    def test_successful_reservation_in_future_interval(self):
        """
        Test: Erfolgreiche Reservierung für ein künftiges Intervall.
        Prüft Status 'active' und Berechnung des Last Pickup Date.
        """
        start = timezone.now() + timedelta(days=5)
        end = timezone.now() + timedelta(days=19)

        result = self.service.create_reservation(
            patron_id=self.adult.id,
            media_id=self.book.id,
            start_date=start,
            end_date=end
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.reservation.status, Reservation.STATUS_ACTIVE)
        self.assertEqual(result.reservation.patron, self.adult)
        self.assertEqual(result.reservation.media_id, self.book.id)

        # Last Pickup Date soll start + 3 Tage sein
        expected_pickup = start + timedelta(days=3)
        self.assertEqual(result.last_pickup_date.date(), expected_pickup.date())

    def test_reservation_denied_when_capacity_exceeded(self):
        """
        Test: Ablehnung wenn im Zielintervall keine freie Kapazität vorhanden ist
        (1 Exemplar vorhanden, aber bereits eine überlappende aktive Reservierung).
        """
        start1 = timezone.now() + timedelta(days=5)
        end1 = timezone.now() + timedelta(days=15)

        # Erste Reservierung belegt das einzige Exemplar
        self.service.create_reservation(
            patron_id=self.adult.id,
            media_id=self.book.id,
            start_date=start1,
            end_date=end1
        )

        # Zweiter Kunde versucht im überlappenden Intervall zu reservieren
        patron2 = Patron.objects.create(
            customer_number="CUST-RES-03",
            name="Zweiter Interessent",
            birthday=date(1990, 1, 1),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="zweiter.res@test.at"
        )
        start2 = timezone.now() + timedelta(days=10)
        end2 = timezone.now() + timedelta(days=20)

        with self.assertRaises(CapacityExceededException):
            self.service.create_reservation(
                patron_id=patron2.id,
                media_id=self.book.id,
                start_date=start2,
                end_date=end2
            )

    def test_reservation_denied_for_fsk_violation(self):
        """
        Test: Ablehnung bei FSK-Verstoß (Jugendlicher reserviert FSK-18 Medium).
        """
        Copy.objects.create(
            barcode="BC-RES-DVD-18",
            media=self.dvd18,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )
        start = timezone.now() + timedelta(days=2)
        end = timezone.now() + timedelta(days=10)

        with self.assertRaises(ReservationFSKViolationException):
            self.service.create_reservation(
                patron_id=self.youth.id,
                media_id=self.dvd18.id,
                start_date=start,
                end_date=end
            )

    def test_reservation_denied_for_invalid_interval(self):
        """
        Test: Ablehnung bei ungültigem Zeitintervall (Start >= Ende oder in der Vergangenheit).
        """
        now = timezone.now()

        # Fall A: In der Vergangenheit
        with self.assertRaises(InvalidIntervalException):
            self.service.create_reservation(
                patron_id=self.adult.id,
                media_id=self.book.id,
                start_date=now - timedelta(days=10),
                end_date=now - timedelta(days=2)
            )

        # Fall B: Start nach Ende
        with self.assertRaises(InvalidIntervalException):
            self.service.create_reservation(
                patron_id=self.adult.id,
                media_id=self.book.id,
                start_date=now + timedelta(days=10),
                end_date=now + timedelta(days=5)
            )

    def test_cancellation_frees_capacity(self):
        """
        Test: Stornierung einer Reservierung gibt die Kapazität sofort wieder frei.
        """
        start = timezone.now() + timedelta(days=5)
        end = timezone.now() + timedelta(days=15)

        res1 = self.service.create_reservation(
            patron_id=self.adult.id,
            media_id=self.book.id,
            start_date=start,
            end_date=end
        )

        # Stornieren
        cancelled_res = self.service.cancel_reservation(reservation_id=res1.reservation.id)
        self.assertEqual(cancelled_res.status, Reservation.STATUS_CANCELLED)

        # Neuer Kunde kann nun für denselben Zeitraum reservieren
        patron2 = Patron.objects.create(
            customer_number="CUST-RES-04",
            name="Nachfolger",
            birthday=date(1995, 2, 2),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="nachfolger@test.at"
        )
        res2 = self.service.create_reservation(
            patron_id=patron2.id,
            media_id=self.book.id,
            start_date=start,
            end_date=end
        )
        self.assertEqual(res2.reservation.status, Reservation.STATUS_ACTIVE)

    def test_expiration_of_outdated_reservations(self):
        """
        Test: Fristablauf (now > last_pickup_date) setzt Reservierung automatisch auf 'expired'
        und gibt Kapazität frei.
        """
        past_time = timezone.now() - timedelta(days=2)
        res = Reservation.objects.create(
            patron=self.adult,
            media=self.book,
            start_date=past_time - timedelta(days=5),
            end_date=past_time + timedelta(days=10),
            last_pickup_date=past_time,  # Abholfrist bereits verstrichen
            status=Reservation.STATUS_ACTIVE
        )

        expired_count = self.service.expire_outdated_reservations()
        self.assertEqual(expired_count, 1)

        res.refresh_from_db()
        self.assertEqual(res.status, Reservation.STATUS_EXPIRED)


class ReservationConcurrencyTests(TransactionTestCase):
    """
    Concurrency-Tests für Use Case 3: Schutz vor Überbuchung bei gleichzeitigen Reservierungsanfragen.
    """

    def test_concurrent_reservations_prevent_overbooking(self):
        """
        Zwei gleichzeitige Reservierungsanfragen für dasselbe Buch (nur 1 Exemplar vorhanden)
        führen dazu, dass genau 1 Reservierung erfolgreich ist und die andere abgewiesen wird.
        """
        from django.db import connection

        location = Location.objects.create(shelf_id=5, compartment="Fach-5E")
        book = Simple_Book.objects.create(
            name="Einzelstück Roman",
            isbn="123-999-000",
            author="Autor Selten"
        )
        Copy.objects.create(
            barcode="BC-UNIQUE-COPY",
            media=book,
            location=location,
            status=Copy.STATUS_AVAILABLE
        )

        p1 = Patron.objects.create(
            customer_number="CUST-CONC-R1",
            name="Kunde 1",
            birthday=date(1990, 1, 1),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="p1@conc.at"
        )
        p2 = Patron.objects.create(
            customer_number="CUST-CONC-R2",
            name="Kunde 2",
            birthday=date(1991, 1, 1),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="p2@conc.at"
        )

        start = timezone.now() + timedelta(days=7)
        end = timezone.now() + timedelta(days=21)

        results = []
        errors = []

        def attempt_reservation(patron_id):
            connection.close()
            if connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA busy_timeout = 5000;")
            service = ReservationService()
            try:
                res = service.create_reservation(
                    patron_id=patron_id,
                    media_id=book.id,
                    start_date=start,
                    end_date=end
                )
                results.append(res)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        t1 = threading.Thread(target=attempt_reservation, args=(p1.id,))
        t2 = threading.Thread(target=attempt_reservation, args=(p2.id,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Genau 1 Reservierung erfolgreich, genau 1 CapacityExceededException
        self.assertEqual(len(results), 1, f"Erwartete 1 Erfolg, Fehler waren: {errors}")
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], CapacityExceededException)
        self.assertEqual(Reservation.objects.filter(media=book, status=Reservation.STATUS_ACTIVE).count(), 1)


class ReservationAPITests(TestCase):
    """
    Test-Suite für die Web- und REST-Endpoints von Use Case 3.
    """

    def setUp(self):
        self.client = Client()
        self.location = Location.objects.create(shelf_id=1, compartment="Fach-A")
        self.patron = Patron.objects.create(
            customer_number="CUST-API-RES",
            name="Web Reservierer",
            birthday=date(1992, 5, 10),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="webres@test.at"
        )
        self.book = Simple_Book.objects.create(
            name="API Reservierungs-Buch",
            isbn="321-654-987",
            author="API Autor"
        )
        Copy.objects.create(
            barcode="BC-API-RES-01",
            media=self.book,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )

    def test_api_create_reservation_success(self):
        """REST API POST /reservations/api/create/ liefert 201 Created."""
        start = (timezone.localdate() + timedelta(days=3)).isoformat()
        end = (timezone.localdate() + timedelta(days=17)).isoformat()

        response = self.client.post(
            reverse('reservations:api_create'),
            data={
                'patron_id': self.patron.id,
                'media_id': self.book.id,
                'start_date': start,
                'end_date': end
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['media_title'], self.book.name)

    def test_api_cancel_reservation_success(self):
        """REST API POST /reservations/api/cancel/ liefert 200 OK und storniert."""
        res = Reservation.objects.create(
            patron=self.patron,
            media=self.book,
            start_date=timezone.now() + timedelta(days=2),
            end_date=timezone.now() + timedelta(days=10),
            last_pickup_date=timezone.now() + timedelta(days=5),
            status=Reservation.STATUS_ACTIVE
        )

        response = self.client.post(
            reverse('reservations:api_cancel'),
            data={'reservation_id': res.id},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        res.refresh_from_db()
        self.assertEqual(res.status, Reservation.STATUS_CANCELLED)
