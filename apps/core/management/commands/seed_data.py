"""
Management-Command zur Bereitstellung initialer Stammdaten (Seed Data / Fixtures)
für Demonstrationen und Tests gemäß SWD-Projekt-Library.pdf (Abschnitt 5).
"""

from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.core.models import (
    Genre, Location, Patron,
    Simple_Book, Specialized_Book, DVD, Music_CD, Magazine,
    Copy, UsageStats
)


class Command(BaseCommand):
    help = 'Erstellt Initialdaten für Medien, Kunden, Standorte und Exemplare.'

    def handle(self, *args, **options):
        self.stdout.write('Erstelle Stammdaten...')

        # 1. Genres anlegen
        g_roman, _ = Genre.objects.get_or_create(
            name='Belletristik / Roman',
            defaults={'daily_overdue_fee': Decimal('0.50'), 'description': 'Romane und Erzählungen'}
        )
        g_fach, _ = Genre.objects.get_or_create(
            name='Fachliteratur / Informatik',
            defaults={'daily_overdue_fee': Decimal('0.70'), 'description': 'Wissenschaftliche Fachbücher'}
        )
        g_film_ab18, _ = Genre.objects.get_or_create(
            name='Action / Thriller (FSK 18)',
            defaults={'daily_overdue_fee': Decimal('1.50'), 'description': 'Filme für Erwachsene'}
        )
        g_musik, _ = Genre.objects.get_or_create(
            name='Klassik / Audio',
            defaults={'daily_overdue_fee': Decimal('0.40'), 'description': 'Musikaufnahmen auf Audio-CD'}
        )
        g_magazin, _ = Genre.objects.get_or_create(
            name='IT-Fachzeitschrift',
            defaults={'daily_overdue_fee': Decimal('0.30'), 'description': 'Periodika'}
        )

        # 2. Standorte anlegen (Regal und Fach)
        loc_1a, _ = Location.objects.get_or_create(shelf_id=1, compartment='Fach-A')
        loc_1b, _ = Location.objects.get_or_create(shelf_id=1, compartment='Fach-B')
        loc_2a, _ = Location.objects.get_or_create(shelf_id=2, compartment='Fach-A')
        loc_3a, _ = Location.objects.get_or_create(shelf_id=3, compartment='Fach-A')
        loc_4a, _ = Location.objects.get_or_create(shelf_id=4, compartment='Fach-A')

        # 3. Kunden (Patrons) anlegen: Erwachsener, Jugendlicher, Student
        p_adult, _ = Patron.objects.get_or_create(
            customer_number='CUST-1001',
            defaults={
                'name': 'Max Mustermann (Erwachsener)',
                'birthday': date(1990, 5, 15),
                'customer_type': Patron.CUSTOMER_TYPE_ADULT,
                'email': 'max.mustermann@example.com',
            }
        )
        p_youth, _ = Patron.objects.get_or_create(
            customer_number='CUST-1002',
            defaults={
                'name': 'Lukas Jugendliche (14 Jahre)',
                'birthday': date(2012, 8, 20),
                'customer_type': Patron.CUSTOMER_TYPE_YOUTH,
                'email': 'lukas.jugend@example.com',
            }
        )
        p_student, _ = Patron.objects.get_or_create(
            customer_number='CUST-1003',
            defaults={
                'name': 'Sophie Studentin',
                'birthday': date(2003, 3, 10),
                'customer_type': Patron.CUSTOMER_TYPE_STUDENT,
                'email': 'sophie.student@example.com',
            }
        )

        # 4. Medien anlegen
        # 4.1 Einfaches Buch
        b_simple, _ = Simple_Book.objects.get_or_create(
            isbn='978-3-16-148410-0',
            defaults={
                'name': 'Der große Roman',
                'description': 'Ein spannender Unterhaltungsroman.',
                'author': 'Johann Schriftsteller',
                'publisher': 'Literaturverlag',
                'book_type': 'Roman',
                'age_limit': 12,
            }
        )
        b_simple.genres.add(g_roman)

        # 4.2 Fachbuch
        b_spec, _ = Specialized_Book.objects.get_or_create(
            isbn='978-0-13-449416-6',
            defaults={
                'name': 'Clean Architecture & Software Design',
                'description': 'Lehrbuch zu Softwareentwurf und Mustern.',
                'author': 'Robert C. Martin',
                'publisher': 'Prentice Hall',
                'subject': 'Informatik & Software Engineering',
                'age_limit': 0,
            }
        )
        b_spec.genres.add(g_fach)

        # 4.3 DVD FSK 18 (Film für Erwachsene)
        dvd_adult, _ = DVD.objects.get_or_create(
            name='Der Actionthriller (FSK 18)',
            defaults={
                'description': 'Altersbeschränkter Spielfilm für Erwachsene.',
                'director': 'John Director',
                'runtime': 125,
                'format': 'Blu-ray / DVD',
                'age_limit': 18,
            }
        )
        dvd_adult.genres.add(g_film_ab18)

        # 4.4 Musik-CD
        cd_music, _ = Music_CD.objects.get_or_create(
            name='Mozart: Symphonien & Meisterwerke',
            defaults={
                'description': 'Klassische Musikaufnahme.',
                'artist': 'Wiener Philharmoniker',
                'track_count': 14,
                'age_limit': 0,
            }
        )
        cd_music.genres.add(g_musik)

        # 4.5 Magazin
        mag, _ = Magazine.objects.get_or_create(
            name='c\'t Magazin für Computertechnik',
            defaults={
                'description': 'IT-Fachzeitschrift Ausgabe 2026/04',
                'edition': 'Ausgabe 2026/04',
                'issn': '0724-8679',
                'age_limit': 0,
            }
        )
        mag.genres.add(g_magazin)

        # 5. Physische Exemplare (Copies) mit Barcodes anlegen
        # 2 Exemplare für einfaches Buch
        c1, _ = Copy.objects.get_or_create(
            barcode='BARCODE-BOOK-001',
            defaults={'media': b_simple, 'location': loc_1a, 'status': Copy.STATUS_AVAILABLE}
        )
        UsageStats.objects.get_or_create(copy=c1, defaults={'total_loans': 0, 'cumulative_duration': 0})

        c2, _ = Copy.objects.get_or_create(
            barcode='BARCODE-BOOK-002',
            defaults={'media': b_simple, 'location': loc_1b, 'status': Copy.STATUS_AVAILABLE}
        )
        UsageStats.objects.get_or_create(copy=c2, defaults={'total_loans': 0, 'cumulative_duration': 0})

        # 1 Exemplar Fachbuch
        c3, _ = Copy.objects.get_or_create(
            barcode='BARCODE-SPEC-001',
            defaults={'media': b_spec, 'location': loc_2a, 'status': Copy.STATUS_AVAILABLE}
        )
        UsageStats.objects.get_or_create(copy=c3, defaults={'total_loans': 0, 'cumulative_duration': 0})

        # 1 Exemplar FSK 18 DVD
        c4, _ = Copy.objects.get_or_create(
            barcode='BARCODE-DVD-18-001',
            defaults={'media': dvd_adult, 'location': loc_3a, 'status': Copy.STATUS_AVAILABLE}
        )
        UsageStats.objects.get_or_create(copy=c4, defaults={'total_loans': 0, 'cumulative_duration': 0})

        # 1 Exemplar Musik CD
        c5, _ = Copy.objects.get_or_create(
            barcode='BARCODE-CD-001',
            defaults={'media': cd_music, 'location': loc_4a, 'status': Copy.STATUS_AVAILABLE}
        )
        UsageStats.objects.get_or_create(copy=c5, defaults={'total_loans': 0, 'cumulative_duration': 0})

        self.stdout.write(self.style.SUCCESS('Stammdaten und Exemplare wurden erfolgreich angelegt!'))
