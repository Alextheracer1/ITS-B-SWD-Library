"""
Use Case 3: Medium reservieren (Reservation)
API & Controller Layer: Web & Kiosk Controller (Django Views)
Interface: IPatronWebAPI
Verantwortlich: Marcel Kitzmantel (3. Autor)

Aufgaben:
- Anzeige von Medien und Auswahl von Zeitintervallen für Vormerkungen
- Entgegennahme und Validierung der Reservierungsanfrage
- Aufruf des Reservation Services
- Fehlerbehandlung (FSK-Fehler, keine freie Kapazität im Intervall, Concurrency-Konflikt)
- Bestätigungsanzeige mit Last Pickup Date (Abholfrist)
- Endpoints/Views für Stornierung von Reservierungen
"""

from datetime import datetime, time
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from apps.core.models import Media, Patron, Reservation
from apps.reservations.forms import ReservationForm
from apps.reservations.reservation_service import (
    ReservationService,
    InvalidIntervalException,
    ReservationFSKViolationException,
    CapacityExceededException,
    ReservationServiceException
)


def reservation_index_view(request):
    """
    Hauptansicht für Reservierungen:
    - Anzeige des Reservierungsformulars mit Zeitintervall-Auswahl
    - Übersicht aller aktiven Vormerkungen mit Stornierungs-Option
    """
    service = ReservationService()
    active_reservations = service.list_active_reservations()
    form = ReservationForm()

    context = {
        'form': form,
        'active_reservations': active_reservations,
        'today': timezone.localdate(),
    }
    return render(request, 'reservations/reservation_form.html', context)


@require_http_methods(["POST"])
def reservation_create_view(request):
    """
    Erstellt eine neue Reservierung über das Webformular.
    """
    form = ReservationForm(request.POST)
    if form.is_valid():
        patron = form.cleaned_data['patron']
        media = form.cleaned_data['media']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']

        # Datum in datetime umwandeln (mit Beginn bzw. Ende des Tages)
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
        end_dt = timezone.make_aware(datetime.combine(end_date, time.max), tz)

        service = ReservationService()
        try:
            result = service.create_reservation(
                patron_id=patron.id,
                media_id=media.id,
                start_date=start_dt,
                end_date=end_dt
            )
            messages.success(request, result.message)
        except InvalidIntervalException as e:
            messages.error(request, f"Intervallfehler: {str(e)}")
        except ReservationFSKViolationException as e:
            messages.error(request, f"FSK-Fehler: {str(e)}")
        except CapacityExceededException as e:
            messages.warning(request, f"Keine Kapazität: {str(e)}")
        except ReservationServiceException as e:
            messages.error(request, f"Fehler bei Reservierung: {str(e)}")
        except Exception as e:
            messages.error(request, f"Systemfehler: {str(e)}")
    else:
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f"{field}: {err}")

    return redirect('reservations:index')


@require_http_methods(["POST"])
def reservation_cancel_view(request, reservation_id):
    """
    Storniert eine bestehende Reservierung und gibt Kapazität frei.
    """
    service = ReservationService()
    try:
        service.cancel_reservation(reservation_id)
        messages.success(request, f"Reservierung #{reservation_id} wurde erfolgreich storniert. Die Kapazität ist wieder frei.")
    except ReservationServiceException as e:
        messages.error(request, f"Stornierung nicht möglich: {str(e)}")
    return redirect('reservations:index')


@api_view(['POST'])
def api_create_reservation(request):
    """
    REST-API Endpoint für Reservierungen:
    POST /reservations/api/create/
    Payload: {"patron_id": 1, "media_id": 2, "start_date": "2026-12-01", "end_date": "2026-12-15"}
    """
    patron_id = request.data.get('patron_id')
    media_id = request.data.get('media_id')
    start_str = request.data.get('start_date')
    end_str = request.data.get('end_date')

    if not all([patron_id, media_id, start_str, end_str]):
        return Response(
            {"error": "Die Parameter 'patron_id', 'media_id', 'start_date' und 'end_date' sind erforderlich."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        tz = timezone.get_current_timezone()
        if 'T' in start_str:
            start_dt = datetime.fromisoformat(start_str)
        else:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(start_str, '%Y-%m-%d').date(), time.min), tz)

        if 'T' in end_str:
            end_dt = datetime.fromisoformat(end_str)
        else:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(end_str, '%Y-%m-%d').date(), time.max), tz)

        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, tz)
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt, tz)
    except ValueError as e:
        return Response({"error": f"Ungültiges Datumsformat: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    service = ReservationService()
    try:
        result = service.create_reservation(
            patron_id=int(patron_id),
            media_id=int(media_id),
            start_date=start_dt,
            end_date=end_dt
        )
        return Response({
            "success": True,
            "reservation_id": result.reservation.id,
            "media_title": result.reservation.media.name,
            "patron_name": result.reservation.patron.name,
            "start_date": result.reservation.start_date.isoformat(),
            "end_date": result.reservation.end_date.isoformat(),
            "last_pickup_date": result.last_pickup_date.isoformat(),
            "available_capacity_remaining": result.available_capacity_remaining,
            "message": result.message,
        }, status=status.HTTP_201_CREATED)
    except ReservationFSKViolationException as e:
        return Response({"error": "FSK_VIOLATION", "message": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except CapacityExceededException as e:
        return Response({"error": "CAPACITY_EXCEEDED", "message": str(e)}, status=status.HTTP_409_CONFLICT)
    except InvalidIntervalException as e:
        return Response({"error": "INVALID_INTERVAL", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except ReservationServiceException as e:
        return Response({"error": "RESERVATION_ERROR", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def api_cancel_reservation(request):
    """
    REST-API Endpoint zum Stornieren einer Reservierung:
    POST /reservations/api/cancel/
    Payload: {"reservation_id": 1}
    """
    reservation_id = request.data.get('reservation_id')
    if not reservation_id:
        return Response({"error": "reservation_id ist erforderlich."}, status=status.HTTP_400_BAD_REQUEST)

    service = ReservationService()
    try:
        res = service.cancel_reservation(int(reservation_id))
        return Response({
            "success": True,
            "reservation_id": res.id,
            "status": res.status,
            "message": f"Reservierung #{res.id} erfolgreich storniert. Kapazität ist wieder freigegeben."
        }, status=status.HTTP_200_OK)
    except ReservationServiceException as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def api_check_capacity(request):
    """
    REST-API Endpoint zur Kapazitätsabfrage für ein Zeitfenster:
    GET /reservations/api/check/?media_id=1&start_date=2026-12-01&end_date=2026-12-15
    """
    media_id = request.GET.get('media_id')
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    if not all([media_id, start_str, end_str]):
        return Response({"error": "Parameter media_id, start_date, end_date erforderlich."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(datetime.strptime(start_str, '%Y-%m-%d').date(), time.min), tz)
        end_dt = timezone.make_aware(datetime.combine(datetime.strptime(end_str, '%Y-%m-%d').date(), time.max), tz)
    except ValueError as e:
        return Response({"error": f"Ungültiges Datumsformat: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    from apps.core.concurrency import ConcurrencyLockManager
    has_cap, free_slots, total = ConcurrencyLockManager.check_and_lock_reservation_capacity(
        media_id=int(media_id),
        start_date=start_dt,
        end_date=end_dt
    )
    return Response({
        "media_id": int(media_id),
        "has_capacity": has_cap,
        "free_slots": free_slots,
        "total_copies": total
    })
