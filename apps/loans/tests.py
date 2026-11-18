"""
Automatisierte Unit-Tests für Use Case 1: Medium ausleihen
Verantwortlich: Alexander Graf (1. Autor)

Zu testende kritische Pfade (gemäß Vorgabeblatt & Projektbeschreibung):
- Erfolgreiche Ausleihe bei verfügbarem Exemplar
- Ablehnung bei FSK-Verstoß (z. B. Jugendlicher versucht FSK-18 DVD zu leihen)
- Ablehnung bei fehlender Verfügbarkeit
- Erfolgreiche Ausleihe mit vorheriger Reservierung
- Berechnung der Leihfrist (4 Wochen Standard vs. 6 Wochen für Studenten bei Fachbüchern)
- Concurrency-Test: Schutz vor Doppelzuweisung des letzten Exemplars bei zeitgleicher Anfrage
- Einhaltung der Best Practices: Test-Isolation, Arrange-Act-Assert (AAA), Boundary/Error Cases
"""

from datetime import date, timedelta
from decimal import Decimal
import threading
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    Genre, Location, Patron, Simple_Book, Specialized_Book, DVD, Copy, Loan, Reservation
)
from apps.loans.loan_service import (
    LoanService,
    FSKViolationException,
    UnavailableMediaException,
    LoanServiceException
)


class LoanServiceTests(TestCase):
    """
    Test-Suite für die Kernlogik des LoanService (Use Case 1).
    """

    def setUp(self):
        """Arrange: Gemeinsame Testdaten für jeden Test isoliert aufbauen."""
        self.service = LoanService()

        # Genre & Standort
        self.genre_roman = Genre.objects.create(
            name="Roman",
            daily_overdue_fee=Decimal("0.50")
        )
        self.genre_thriller = Genre.objects.create(
            name="Thriller (FSK 18)",
            daily_overdue_fee=Decimal("1.50")
        )
        self.location = Location.objects.create(shelf_id=1, compartment="Fach-1A")

        # Kunden: Erwachsener, Jugendlicher (14 Jahre), Student
        self.adult = Patron.objects.create(
            customer_number="CUST-TEST-01",
            name="Erwachsener Max",
            birthday=date(1990, 1, 1),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="max@test.at"
        )
        self.youth = Patron.objects.create(
            customer_number="CUST-TEST-02",
            name="Jugendlicher Tim",
            birthday=timezone.localdate() - timedelta(days=14 * 365),
            customer_type=Patron.CUSTOMER_TYPE_YOUTH,
            email="tim@test.at"
        )
        self.student = Patron.objects.create(
            customer_number="CUST-TEST-03",
            name="Studentin Laura",
            birthday=date(2002, 5, 20),
            customer_type=Patron.CUSTOMER_TYPE_STUDENT,
            email="laura@test.at"
        )

        # Medien
        self.simple_book = Simple_Book.objects.create(
            name="Der Wanderer",
            isbn="111-222-333",
            author="Autor Eins",
            age_limit=0
        )
        self.simple_book.genres.add(self.genre_roman)

        self.specialized_book = Specialized_Book.objects.create(
            name="Kompakte Algorithmen",
            isbn="444-555-666",
            author="Prof. Test",
            subject="Informatik",
            age_limit=0
        )
        self.specialized_book.genres.add(self.genre_roman)

        self.dvd_18 = DVD.objects.create(
            name="Action 18+",
            director="Director John",
            runtime=110,
            age_limit=18
        )
        self.dvd_18.genres.add(self.genre_thriller)

    def test_successful_loan_of_available_copy(self):
        """
        Test: Erfolgreiche Ausleihe bei vorhandenem Exemplar.
        Prüft Zuweisung, Statuswechsel auf 'on_loan' und Rückgabe von Regal/Fach.
        """
        # Arrange
        copy = Copy.objects.create(
            barcode="BC-001",
            media=self.simple_book,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )

        # Act
        result = self.service.borrow_media(patron_id=self.adult.id, media_id=self.simple_book.id)

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.copy.id, copy.id)
        self.assertEqual(result.shelf_id, 1)
        self.assertEqual(result.compartment, "Fach-1A")

        # Datenbankzustand verifizieren
        copy.refresh_from_db()
        self.assertEqual(copy.status, Copy.STATUS_ON_LOAN)

        loan = Loan.objects.get(copy=copy)
        self.assertEqual(loan.patron, self.adult)
        self.assertEqual(loan.status, Loan.STATUS_ACTIVE)

    def test_loan_denied_for_fsk_violation(self):
        """
        Test: Ablehnung bei FSK-Verstoß.
        Jugendlicher (14 J.) darf keine FSK-18 DVD ausleihen.
        """
        # Arrange
        Copy.objects.create(
            barcode="BC-DVD-01",
            media=self.dvd_18,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )

        # Act & Assert
        with self.assertRaises(FSKViolationException):
            self.service.borrow_media(patron_id=self.youth.id, media_id=self.dvd_18.id)

        # Es darf kein Loan in der DB existieren
        self.assertEqual(Loan.objects.count(), 0)

    def test_loan_denied_when_no_copy_available(self):
        """
        Test: Ablehnung bei fehlender Verfügbarkeit (kein Exemplar im Status 'available').
        """
        # Arrange: Ein Exemplar existiert, ist aber bereits verliehen
        Copy.objects.create(
            barcode="BC-BOOK-BORROWED",
            media=self.simple_book,
            location=self.location,
            status=Copy.STATUS_ON_LOAN
        )

        # Act & Assert
        with self.assertRaises(UnavailableMediaException):
            self.service.borrow_media(patron_id=self.adult.id, media_id=self.simple_book.id)

        self.assertEqual(Loan.objects.count(), 0)

    def test_standard_loan_period_calculation_four_weeks(self):
        """
        Test: Standard-Leihfrist beträgt 4 Wochen (28 Tage).
        """
        # Arrange
        Copy.objects.create(
            barcode="BC-STD-01",
            media=self.simple_book,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )

        # Act
        result = self.service.borrow_media(patron_id=self.adult.id, media_id=self.simple_book.id)

        # Assert
        expected_days = 28
        actual_delta = result.loan.planned_return_date.date() - timezone.localdate()
        self.assertEqual(actual_delta.days, expected_days)

    def test_student_loan_period_for_specialized_book_six_weeks(self):
        """
        Test: Studierende erhalten für Fachbücher eine Leihfrist von 6 Wochen (42 Tage).
        """
        # Arrange
        Copy.objects.create(
            barcode="BC-SPEC-01",
            media=self.specialized_book,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )

        # Act
        result = self.service.borrow_media(patron_id=self.student.id, media_id=self.specialized_book.id)

        # Assert
        expected_days = 42
        actual_delta = result.loan.planned_return_date.date() - timezone.localdate()
        self.assertEqual(actual_delta.days, expected_days)

    def test_loan_fulfills_prior_reservation(self):
        """
        Test: Erfolgreiche Ausleihe referenziert eine vorherige Reservierung und markiert sie als erfüllt.
        """
        # Arrange
        copy = Copy.objects.create(
            barcode="BC-RES-01",
            media=self.simple_book,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )
        reservation = Reservation.objects.create(
            patron=self.adult,
            media=self.simple_book,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            last_pickup_date=timezone.now() + timedelta(days=3),
            status=Reservation.STATUS_ACTIVE
        )

        # Act
        result = self.service.borrow_media(
            patron_id=self.adult.id,
            media_id=self.simple_book.id,
            reservation_id=reservation.id
        )

        # Assert
        self.assertEqual(result.loan.reservation, reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.STATUS_FULFILLED)


class LoanConcurrencyTests(TransactionTestCase):
    """
    Spezifische Multi-Threading / Concurrency-Tests unter Verwendung von TransactionTestCase.
    """

    def test_concurrency_prevention_of_double_allocation(self):
        """
        Test: Concurrency Control - Bei zeitgleichen Anfragen auf das letzte verbleibende Exemplar
        wird eine Doppelzuweisung verhindert. Genau 1 Anfrage gelingt, die andere scheitert.
        """
        from django.db import connection

        # Arrange: Nur ein einziges Exemplar vorhanden
        location = Location.objects.create(shelf_id=1, compartment="Fach-1A")
        book = Simple_Book.objects.create(
            name="Der Wanderer",
            isbn="111-222-333",
            author="Autor Eins",
            age_limit=0
        )
        Copy.objects.create(
            barcode="BC-LAST-COPY",
            media=book,
            location=location,
            status=Copy.STATUS_AVAILABLE
        )

        patron1 = Patron.objects.create(
            customer_number="CUST-CONC-01",
            name="Erster Kunde",
            birthday=date(1990, 1, 1),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="erster@test.at"
        )

        patron2 = Patron.objects.create(
            customer_number="CUST-CONC-02",
            name="Zweiter Kunde",
            birthday=date(1992, 2, 2),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="zweiter@test.at"
        )

        results = []
        errors = []

        def attempt_loan(patron_id):
            connection.close()  # sicherstellen, dass der Thread eine frische DB-Verbindung nutzt
            if connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA busy_timeout = 5000;")
            service = LoanService()
            try:
                res = service.borrow_media(patron_id=patron_id, media_id=book.id)
                results.append(res)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        # Zwei parallele Threads starten
        t1 = threading.Thread(target=attempt_loan, args=(patron1.id,))
        t2 = threading.Thread(target=attempt_loan, args=(patron2.id,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Genau 1 erfolgreiche Ausleihe und 1 Fehler
        self.assertEqual(len(results), 1, f"Erwartete 1 Erfolg, Fehler waren: {errors}")
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], UnavailableMediaException)
        self.assertEqual(Loan.objects.count(), 1)


class LoanWebAndAPITests(TestCase):
    """
    Test-Suite für die Web- und REST-Controller von Use Case 1.
    """

    def setUp(self):
        self.client = Client()
        self.location = Location.objects.create(shelf_id=1, compartment="Fach-A")
        self.adult = Patron.objects.create(
            customer_number="CUST-WEB-01",
            name="Web Kunde",
            birthday=date(1995, 3, 15),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="web@test.at"
        )
        self.book = Simple_Book.objects.create(
            name="Web Test Book",
            isbn="999-888-777",
            author="Web Author"
        )
        self.copy = Copy.objects.create(
            barcode="BC-WEB-001",
            media=self.book,
            location=self.location,
            status=Copy.STATUS_AVAILABLE
        )

    def test_catalog_view_renders_correctly(self):
        """Katalog-View lädt fehlerfrei und zeigt Medien an."""
        response = self.client.get(reverse('loans:catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Web Test Book")

    def test_web_checkout_flow(self):
        """Web-Checkout per POST erstellt Loan und leitet weiter."""
        response = self.client.post(reverse('loans:checkout'), {
            'patron': self.adult.id,
            'media': self.book.id
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Loan.objects.filter(patron=self.adult).count(), 1)

    def test_api_checkout_success(self):
        """REST API Checkout /loans/api/checkout/ gibt JSON 201 Created zurück."""
        response = self.client.post(
            reverse('loans:api_checkout'),
            data={'patron_id': self.adult.id, 'media_id': self.book.id},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['barcode'], "BC-WEB-001")
        self.assertEqual(data['shelf_id'], 1)
