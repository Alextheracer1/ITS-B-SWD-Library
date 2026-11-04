"""
Datenmodelle für das LiBros Bibliothekssystem.
Gemäß Spezifikation in SWD-Projekt-Library.pdf (Kapitel 3: Data Model)
und Klassendiagramm in SWD-LiBros.pdf (Kapitel 4.1: Klassendiagramme).
"""

from decimal import Decimal
from django.db import models
from django.utils import timezone


# ==============================================================================
# Stammdaten: Genre & Standort
# ==============================================================================

class Genre(models.Model):
    """
    Genre-Kategorie für Medien.
    Ermöglicht flexible Zuordnung und genrespezifische Gebührensätze.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Genre-Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    daily_overdue_fee = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.50"),
        verbose_name="Tägliche Versäumnisgebühr (€)"
    )

    class Meta:
        verbose_name = "Genre"
        verbose_name_plural = "Genres"

    def __str__(self):
        return self.name


class Location(models.Model):
    """
    Physischer Bibliotheksstandort für Exemplare (Copy).
    Besteht aus Regal-Identifikator (shelf_id) und Fach (compartment).
    Team (3) Anforderung: Jedes physische Exemplar ist genau einem Fach zugewiesen.
    """
    shelf_id = models.IntegerField(verbose_name="Regal-ID")
    compartment = models.CharField(max_length=50, verbose_name="Fach / Compartment")

    class Meta:
        verbose_name = "Standort"
        verbose_name_plural = "Standorte"
        unique_together = ('shelf_id', 'compartment')

    def __str__(self):
        return f"Regal {self.shelf_id}, Fach {self.compartment}"


# ==============================================================================
# Stammdaten: Kunden / Patrons
# ==============================================================================

class Patron(models.Model):
    """
    Bibliotheksbenutzer (Kunde).
    Unterscheidet Kundentypen (Erwachsene, Jugendliche 10-18, Studierende).
    Enthält Geburtsdatum für FSK-Prüfungen.
    """
    CUSTOMER_TYPE_ADULT = 'adult'
    CUSTOMER_TYPE_YOUTH = 'youth'
    CUSTOMER_TYPE_STUDENT = 'student'

    CUSTOMER_TYPE_CHOICES = [
        (CUSTOMER_TYPE_ADULT, 'Erwachsener (Adult)'),
        (CUSTOMER_TYPE_YOUTH, 'Jugendlicher (10-18 Jahre)'),
        (CUSTOMER_TYPE_STUDENT, 'Studierender (Student)'),
    ]

    customer_number = models.CharField(max_length=50, unique=True, verbose_name="Kundennummer")
    name = models.CharField(max_length=200, verbose_name="Name")
    birthday = models.DateField(verbose_name="Geburtsdatum")
    customer_type = models.CharField(
        max_length=20,
        choices=CUSTOMER_TYPE_CHOICES,
        default=CUSTOMER_TYPE_ADULT,
        verbose_name="Kundentyp"
    )
    email = models.EmailField(unique=True, verbose_name="E-Mail")
    outstanding_fees = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Offene Gebühren (€)"
    )

    class Meta:
        verbose_name = "Kunde"
        verbose_name_plural = "Kunden"

    def __str__(self):
        return f"{self.name} ({self.customer_number}) - {self.get_customer_type_display()}"

    def calculate_age(self):
        today = timezone.localdate()
        return today.year - self.birthday.year - ((today.month, today.day) < (self.birthday.month, self.birthday.day))


# ==============================================================================
# Stammdaten: Medien & Medientypen (Klassenhierarchie)
# ==============================================================================

class Media(models.Model):
    """
    Basisklasse für Medien (Titelebene / abstraktes Medium).
    Kunden leihen und reservieren auf dieser Titelebene.
    """
    STATE_AVAILABLE = 'available'
    STATE_BORROWED = 'borrowed'
    STATE_RESERVED = 'reserved'
    STATE_MAINTENANCE = 'maintenance'

    STATE_CHOICES = [
        (STATE_AVAILABLE, 'Verfügbar'),
        (STATE_BORROWED, 'Ausgeliehen'),
        (STATE_RESERVED, 'Reserviert'),
        (STATE_MAINTENANCE, 'Wartung / Ausgesondert'),
    ]

    name = models.CharField(max_length=255, verbose_name="Titel / Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    rating = models.FloatField(default=0.0, verbose_name="Bewertung")
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default=STATE_AVAILABLE, verbose_name="Status")
    rent_count = models.IntegerField(default=0, verbose_name="Ausleihzähler")
    age_limit = models.IntegerField(default=0, verbose_name="FSK-Altersfreigabe")
    genres = models.ManyToManyField(Genre, related_name='media_items', verbose_name="Genres")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        verbose_name = "Medium"
        verbose_name_plural = "Medien"

    def __str__(self):
        return f"{self.name} (FSK {self.age_limit})"


class Book(Media):
    """
    Buch-Medium (einfache und Fachbücher).
    """
    isbn = models.CharField(max_length=20, unique=True, verbose_name="ISBN")
    author = models.CharField(max_length=255, verbose_name="Autor(en)")
    publisher = models.CharField(max_length=255, blank=True, verbose_name="Verlag")

    class Meta:
        verbose_name = "Buch"
        verbose_name_plural = "Bücher"


class Simple_Book(Book):
    """
    Allgemeines Buch (z. B. Romane, Sachbücher).
    Standard-Leihfrist: 4 Wochen.
    """
    book_type = models.CharField(max_length=100, default="Roman / Sachbuch", verbose_name="Buchtyp")

    class Meta:
        verbose_name = "Einfaches Buch"
        verbose_name_plural = "Einfache Bücher"


class Specialized_Book(Book):
    """
    Fachbuch (z. B. Medizin, Recht, Technik).
    Studierende erhalten erweiterte Leihfrist (bis zu 6 Wochen).
    """
    subject = models.CharField(max_length=200, verbose_name="Fachbereich")

    class Meta:
        verbose_name = "Fachbuch"
        verbose_name_plural = "Fachbücher"


class Music_CD(Media):
    """
    Musik-CD Medium.
    """
    artist = models.CharField(max_length=255, verbose_name="Künstler / Interpret")
    track_count = models.IntegerField(default=1, verbose_name="Anzahl Tracks")

    class Meta:
        verbose_name = "Musik-CD"
        verbose_name_plural = "Musik-CDs"


class DVD(Media):
    """
    Film / DVD Medium (auch Filme für Erwachsene mit FSK 18).
    """
    director = models.CharField(max_length=255, verbose_name="Regisseur")
    runtime = models.IntegerField(verbose_name="Laufzeit in Minuten")
    format = models.CharField(max_length=50, default="DVD", verbose_name="Format")

    class Meta:
        verbose_name = "DVD / Film"
        verbose_name_plural = "DVDs / Filme"


class Magazine(Media):
    """
    Zeitschrift / Magazin (periodische Publikation).
    """
    edition = models.CharField(max_length=100, verbose_name="Ausgabe / Edition")
    issn = models.CharField(max_length=20, blank=True, verbose_name="ISSN")

    class Meta:
        verbose_name = "Magazin / Zeitschrift"
        verbose_name_plural = "Magazine / Zeitschriften"


# ==============================================================================
# Physische Exemplare & Nutzungsstatistiken
# ==============================================================================

class Copy(models.Model):
    """
    Physisches Exemplar eines abstrakten Mediums.
    Jedes Exemplar besitzt einen eindeutigen Barcode und steht an genau einem Fach.
    """
    STATUS_AVAILABLE = 'available'
    STATUS_ON_LOAN = 'on_loan'
    STATUS_RESERVED = 'reserved'
    STATUS_WITHDRAWN = 'withdrawn/replacement'
    STATUS_MAINTENANCE = 'maintenance'

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Verfügbar'),
        (STATUS_ON_LOAN, 'Ausgeliehen'),
        (STATUS_RESERVED, 'Reserviert'),
        (STATUS_WITHDRAWN, 'Zur Aussonderung / Ersatz'),
        (STATUS_MAINTENANCE, 'Wartung'),
    ]

    barcode = models.CharField(max_length=100, unique=True, verbose_name="Barcode / Copy-ID")
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name='copies', verbose_name="Medium")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='copies', verbose_name="Standort")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_AVAILABLE, verbose_name="Status")
    usage_count = models.IntegerField(default=0, verbose_name="Nutzungszähler")

    class Meta:
        verbose_name = "Physisches Exemplar"
        verbose_name_plural = "Physische Exemplare"

    def __str__(self):
        return f"{self.media.name} [Barcode: {self.barcode}] - {self.get_status_display()}"


class UsageStats(models.Model):
    """
    Nutzungsstatistik pro physischem Exemplar.
    Verwaltet Anzahl der Ausleihen und kumulierte Ausleihdauer für Abnutzungsschwellen.
    """
    copy = models.OneToOneField(Copy, on_delete=models.CASCADE, related_name='usage_stats', verbose_name="Exemplar")
    total_loans = models.IntegerField(default=0, verbose_name="Gesamtzahl Ausleihen")
    cumulative_duration = models.IntegerField(default=0, verbose_name="Kumulierte Ausleihdauer (Tage)")

    class Meta:
        verbose_name = "Nutzungsstatistik"
        verbose_name_plural = "Nutzungsstatistiken"

    def __str__(self):
        return f"Statistik für {self.copy.barcode}: {self.total_loans} Ausleihen, {self.cumulative_duration} Tage"


# ==============================================================================
# Transaktionsdaten: Ausleihe & Reservierung
# ==============================================================================

class Reservation(models.Model):
    """
    Reservierung (Hold) für ein Medium auf Titelebene durch einen Kunden.
    UC-03: Reservierung
    """
    STATUS_ACTIVE = 'active'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktiv'),
        (STATUS_FULFILLED, 'Eingelöst (in Ausleihe übergegangen)'),
        (STATUS_CANCELLED, 'Storniert'),
        (STATUS_EXPIRED, 'Abgelaufen (Pickup-Frist verstrichen)'),
    ]

    patron = models.ForeignKey(Patron, on_delete=models.CASCADE, related_name='reservations', verbose_name="Kunde")
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name='reservations', verbose_name="Medium")
    reservation_timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Reservierungszeitpunkt")
    start_date = models.DateTimeField(null=True, blank=True, verbose_name="Intervall-Start")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Intervall-Ende")
    last_pickup_date = models.DateTimeField(verbose_name="Abholfrist (Last Pickup Date)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, verbose_name="Status")

    class Meta:
        verbose_name = "Reservierung"
        verbose_name_plural = "Reservierungen"

    def __str__(self):
        return f"Reservierung #{self.id}: {self.patron.name} für {self.media.name} (Frist: {self.last_pickup_date})"


class Loan(models.Model):
    """
    Ausleihvorgang für ein physisches Exemplar.
    UC-01: Ausleihe & UC-02: Rückgabe
    """
    STATUS_ACTIVE = 'active'
    STATUS_CLOSED = 'closed'
    STATUS_OVERDUE = 'overdue'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktiv / Ausgeliehen'),
        (STATUS_CLOSED, 'Abgeschlossen / Zurückgegeben'),
        (STATUS_OVERDUE, 'Überfällig'),
    ]

    patron = models.ForeignKey(Patron, on_delete=models.CASCADE, related_name='loans', verbose_name="Kunde")
    copy = models.ForeignKey(Copy, on_delete=models.CASCADE, related_name='loans', verbose_name="Exemplar")
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resulting_loans',
        verbose_name="Ursprüngliche Reservierung"
    )
    checkout_timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Ausleihzeitpunkt")
    planned_return_date = models.DateTimeField(verbose_name="Geplantes Rückgabedatum")
    actual_return_timestamp = models.DateTimeField(null=True, blank=True, verbose_name="Tatsächlicher Rückgabezeitpunkt")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, verbose_name="Status")
    overdue_fee = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Versäumnisgebühr (€)"
    )

    class Meta:
        verbose_name = "Ausleihe"
        verbose_name_plural = "Ausleihen"

    def __str__(self):
        return f"Ausleihe #{self.id}: {self.copy.barcode} an {self.patron.name} (Fällig: {self.planned_return_date})"
