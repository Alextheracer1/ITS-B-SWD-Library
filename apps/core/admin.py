"""
Django Admin Registrierung für Stammdaten und Transaktionsdaten.
"""

from django.contrib import admin
from .models import (
    Genre, Location, Patron, Media,
    Book, Simple_Book, Specialized_Book,
    Music_CD, DVD, Magazine,
    Copy, UsageStats, Reservation, Loan
)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'daily_overdue_fee')
    search_fields = ('name',)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('shelf_id', 'compartment')
    list_filter = ('shelf_id',)


@admin.register(Patron)
class PatronAdmin(admin.ModelAdmin):
    list_display = ('customer_number', 'name', 'customer_type', 'birthday', 'email', 'outstanding_fees')
    list_filter = ('customer_type',)
    search_fields = ('customer_number', 'name', 'email')


class CopyInline(admin.TabularInline):
    model = Copy
    extra = 1


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ('name', 'age_limit', 'rating', 'state', 'rent_count')
    list_filter = ('age_limit', 'state', 'genres')
    search_fields = ('name',)


@admin.register(Simple_Book)
class SimpleBookAdmin(admin.ModelAdmin):
    list_display = ('name', 'isbn', 'author', 'book_type', 'age_limit')


@admin.register(Specialized_Book)
class SpecializedBookAdmin(admin.ModelAdmin):
    list_display = ('name', 'isbn', 'author', 'subject', 'age_limit')


@admin.register(Music_CD)
class MusicCDAdmin(admin.ModelAdmin):
    list_display = ('name', 'artist', 'track_count', 'age_limit')


@admin.register(DVD)
class DVDAdmin(admin.ModelAdmin):
    list_display = ('name', 'director', 'runtime', 'format', 'age_limit')


@admin.register(Magazine)
class MagazineAdmin(admin.ModelAdmin):
    list_display = ('name', 'edition', 'issn', 'age_limit')


@admin.register(Copy)
class CopyAdmin(admin.ModelAdmin):
    list_display = ('barcode', 'media', 'location', 'status', 'usage_count')
    list_filter = ('status', 'location__shelf_id')
    search_fields = ('barcode', 'media__name')


@admin.register(UsageStats)
class UsageStatsAdmin(admin.ModelAdmin):
    list_display = ('copy', 'total_loans', 'cumulative_duration')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'patron', 'media', 'reservation_timestamp', 'last_pickup_date', 'status')
    list_filter = ('status',)
    search_fields = ('patron__name', 'media__name')


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('id', 'patron', 'copy', 'checkout_timestamp', 'planned_return_date', 'actual_return_timestamp', 'status', 'overdue_fee')
    list_filter = ('status',)
    search_fields = ('patron__name', 'copy__barcode')
