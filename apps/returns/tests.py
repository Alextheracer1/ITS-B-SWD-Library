"""
Automatisierte Unit-Tests für Use Case 2: Medium zurückgeben
Verantwortlich: David Leberbauer (2. Autor)

Zu testende kritische Pfade (gemäß Vorgabeblatt & Projektbeschreibung):
- Erfolgreiche Rückgabe eines fristgerecht ausgeliehenen Exemplars
- Rückgabe mit Fristüberschreitung: Korrekte Berechnung der Versäumnisgebühren (höchster Genre-Tarif)
  und Buchung auf Kundenkonto
- Korrekte Aktualisierung der Nutzungsstatistik (total_loans +1, cumulative_duration)
- Erreichen des Abnutzungsschwellenwerts (Usage Threshold): Statusübergang auf 'withdrawn/replacement'
- Ablehnung bei unbekanntem Barcode oder nicht ausgeliehenem Exemplar (keine Datenänderung)
- Einhaltung der Best Practices: Test-Isolation, Arrange-Act-Assert (AAA), Boundary/Error Cases
"""

from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    Genre, Location, Patron, Simple_Book, DVD, Copy, Loan, UsageStats
)
from apps.returns.return_service import (
    ReturnService,
    InvalidBarcodeException,
    NoActiveLoanException
)


class ReturnServiceTests(TestCase):
    """
    Test-Suite für die Kernlogik des ReturnService (Use Case 2).
    """

    def setUp(self):
        self.service = ReturnService()
        self.location = Location.objects.create(shelf_id=2, compartment="Fach-2B")

        # Genres mit unterschiedlichen Versäumnisgebühren
        self.genre_standard = Genre.objects.create(
            name="Sachbuch",
            daily_overdue_fee=Decimal("0.50")
        )
        self.genre_premium = Genre.objects.create(
            name="Bestseller / Premium",
            daily_overdue_fee=Decimal("1.20")
        )

        self.patron = Patron.objects.create(
            customer_number="CUST-RET-01",
            name="Hans Rückgeber",
            birthday=date(1985, 4, 12),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="hans@rueckgabe.at",
            outstanding_fees=Decimal("0.00")
        )

        self.book = Simple_Book.objects.create(
            name="Erfolgreich Testen",
            isbn="333-444-555",
            author="Dev Expert",
            age_limit=0
        )
        self.book.genres.add(self.genre_standard)
        self.book.genres.add(self.genre_premium)  # Höchster Tarif ist 1.20 €

        self.copy = Copy.objects.create(
            barcode="BC-RET-001",
            media=self.book,
            location=self.location,
            status=Copy.STATUS_ON_LOAN,
            usage_count=5
        )
        self.stats = UsageStats.objects.create(
            copy=self.copy,
            total_loans=5,
            cumulative_duration=50
        )

    def test_successful_on_time_return(self):
        """
        Test: Erfolgreiche Rückgabe innerhalb der Frist.
        Keine Gebühren, Status wird 'available', Loan wird 'closed', Stats aktualisiert.
        """
        # Arrange: Ausleihe fällig in 7 Tagen
        loan = Loan.objects.create(
            patron=self.patron,
            copy=self.copy,
            planned_return_date=timezone.now() + timedelta(days=7),
            status=Loan.STATUS_ACTIVE
        )

        # Act
        result = self.service.process_return(barcode=self.copy.barcode)

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.overdue_days, 0)
        self.assertEqual(result.overdue_fee, Decimal("0.00"))
        self.assertFalse(result.is_withdrawn)

        # Loan prüfen
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.STATUS_CLOSED)
        self.assertIsNotNone(loan.actual_return_timestamp)

        # Copy & Stats prüfen
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, Copy.STATUS_AVAILABLE)
        self.assertEqual(self.copy.usage_count, 6)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.total_loans, 6)
        self.assertGreater(self.stats.cumulative_duration, 50)

        # Kundenkonto prüfen: 0.00 € Gebühren
        self.patron.refresh_from_db()
        self.assertEqual(self.patron.outstanding_fees, Decimal("0.00"))

    def test_overdue_return_calculates_and_charges_highest_genre_fee(self):
        """
        Test: Rückgabe mit Fristüberschreitung.
        Ermittelt Überziehungstage und berechnet Gebühr mit dem höchsten Genre-Tarif (1.20 € / Tag).
        Bucht die Gebühr auf das Kundenkonto.
        """
        # Arrange: Rückgabedatum war vor 4 Tagen
        overdue_days_count = 4
        planned_date = timezone.now() - timedelta(days=overdue_days_count)
        loan = Loan.objects.create(
            patron=self.patron,
            copy=self.copy,
            planned_return_date=planned_date,
            status=Loan.STATUS_ACTIVE
        )

        # Act
        return_time = timezone.now()
        result = self.service.process_return(barcode=self.copy.barcode, return_timestamp=return_time)

        # Assert: 4 Tage * 1.20 € = 4.80 €
        expected_fee = Decimal("4.80")
        self.assertEqual(result.overdue_days, overdue_days_count)
        self.assertEqual(result.overdue_fee, expected_fee)

        # Auf Kundenkonto gebucht
        self.patron.refresh_from_db()
        self.assertEqual(self.patron.outstanding_fees, expected_fee)

        # Loan aktualisiert
        loan.refresh_from_db()
        self.assertEqual(loan.overdue_fee, expected_fee)
        self.assertEqual(loan.status, Loan.STATUS_CLOSED)

    def test_usage_threshold_reached_transitions_to_withdrawn(self):
        """
        Test: Erreichen des Abnutzungsschwellenwerts (Usage Threshold).
        Wenn die maximale Nutzungsanzahl (z. B. 50) erreicht ist, wechselt der Status
        des Exemplars auf 'withdrawn/replacement' statt 'available'.
        """
        # Arrange: Copy steht kurz vor dem Schwellenwert 50 (bereits 49 Ausleihen)
        self.copy.usage_count = 49
        self.copy.save(update_fields=['usage_count'])
        self.stats.total_loans = 49
        self.stats.save(update_fields=['total_loans'])

        Loan.objects.create(
            patron=self.patron,
            copy=self.copy,
            planned_return_date=timezone.now() + timedelta(days=14),
            status=Loan.STATUS_ACTIVE
        )

        # Act: Durch diese Rückgabe wird total_loans = 50 erreicht
        result = self.service.process_return(barcode=self.copy.barcode)

        # Assert
        self.assertTrue(result.is_withdrawn)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, Copy.STATUS_WITHDRAWN)
        self.assertEqual(self.copy.usage_count, 50)

    def test_denial_on_unknown_barcode(self):
        """
        Test: Ablehnung bei unbekanntem Barcode.
        Server verweigert Annahme und verändert keine Daten.
        """
        # Act & Assert
        with self.assertRaises(InvalidBarcodeException):
            self.service.check_return_eligibility("NON-EXISTING-BARCODE")

        with self.assertRaises(InvalidBarcodeException):
            self.service.process_return("NON-EXISTING-BARCODE")

    def test_denial_on_copy_without_active_loan(self):
        """
        Test: Ablehnung wenn für das Exemplar kein aktiver Loan vorliegt
        (z. B. Exemplar steht bereits im Regal mit Status 'available').
        """
        # Arrange
        self.copy.status = Copy.STATUS_AVAILABLE
        self.copy.save(update_fields=['status'])

        # Act & Assert
        with self.assertRaises(NoActiveLoanException):
            self.service.check_return_eligibility(self.copy.barcode)

        with self.assertRaises(NoActiveLoanException):
            self.service.process_return(self.copy.barcode)


class ReturnStationAPITests(TestCase):
    """
    Test-Suite für die REST-API der Rückgabestation (Endpoints 1 und 2).
    """

    def setUp(self):
        self.client = Client()
        self.location = Location.objects.create(shelf_id=3, compartment="Fach-3C")
        self.patron = Patron.objects.create(
            customer_number="CUST-API-01",
            name="API Tester",
            birthday=date(1991, 7, 20),
            customer_type=Patron.CUSTOMER_TYPE_ADULT,
            email="api@test.at"
        )
        self.book = Simple_Book.objects.create(
            name="Return Station Handbuch",
            isbn="888-999-000",
            author="Dev Return"
        )
        self.copy = Copy.objects.create(
            barcode="BC-API-RET-01",
            media=self.book,
            location=self.location,
            status=Copy.STATUS_ON_LOAN
        )
        self.loan = Loan.objects.create(
            patron=self.patron,
            copy=self.copy,
            planned_return_date=timezone.now() + timedelta(days=5),
            status=Loan.STATUS_ACTIVE
        )

    def test_api_check_eligibility_success(self):
        """Endpoint 1 (Annahmeanfrage) liefert Status 200 und eligible=True."""
        response = self.client.post(
            reverse('returns:api_check'),
            data={'barcode': self.copy.barcode},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['eligible'])
        self.assertEqual(data['barcode'], self.copy.barcode)
        self.assertEqual(data['media_title'], self.book.name)

    def test_api_check_eligibility_unknown_barcode(self):
        """Endpoint 1 mit unbekanntem Barcode liefert 404 Not Found."""
        response = self.client.post(
            reverse('returns:api_check'),
            data={'barcode': 'DOES-NOT-EXIST'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data['eligible'])
        self.assertEqual(data['error_code'], 'INVALID_BARCODE')

    def test_api_confirm_return_success(self):
        """Endpoint 2 (Rückgabebestätigung) schließt Loan erfolgreich ab."""
        response = self.client.post(
            reverse('returns:api_confirm'),
            data={'barcode': self.copy.barcode},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], Copy.STATUS_AVAILABLE)

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, Loan.STATUS_CLOSED)
