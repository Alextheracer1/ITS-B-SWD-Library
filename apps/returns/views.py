"""
Use Case 2: Medium zurückgeben (Return)
API & Controller Layer: Return Station API (REST / HTTP Endpoints) & Views
Interface: IReturnStationAPI
Verantwortlich: David Leberbauer (2. Autor)

Aufgaben:
- Endpoint 1 (Annahmeanfrage): Prüft, ob Exemplar anhand des gescannten Barcodes angenommen werden darf
  (Exemplar existiert, gehört zur Bibliothek, offener Loan vorhanden).
- Endpoint 2 (Rückgabebestätigung): Schließt Rückgabe ab, bucht ggf. Überziehungsgebühren,
  aktualisiert Nutzungsstatistik und Exemplarstatus.
- Bereitstellung der View für die HTML-Hardwaresimulation der Rückgabestation.
"""

from datetime import datetime
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from apps.core.models import Loan, Copy
from apps.returns.forms import BarcodeScanForm
from apps.returns.return_service import (
    ReturnService,
    InvalidBarcodeException,
    NoActiveLoanException,
    ReturnServiceException
)


def return_station_view(request):
    """
    Rendert die HTML-Simulation der automatisierten Rückgabestation.
    Zeigt die Hardwareschnittstelle sowie aktuell offene Ausleihen zur einfachen Testbedienung an.
    """
    active_loans = Loan.objects.filter(
        status=Loan.STATUS_ACTIVE
    ).select_related('patron', 'copy', 'copy__media', 'copy__location')

    form = BarcodeScanForm()
    now = timezone.now()

    loans_data = []
    for l in active_loans:
        is_overdue = now > l.planned_return_date
        overdue_days = (now.date() - l.planned_return_date.date()).days if is_overdue else 0
        loans_data.append({
            'loan': l,
            'is_overdue': is_overdue,
            'overdue_days': overdue_days
        })

    context = {
        'form': form,
        'active_loans': loans_data,
        'current_time': now,
    }
    return render(request, 'returns/return_station.html', context)


@require_http_methods(["POST"])
def process_return_web(request):
    """
    Standard HTTP-POST Fallback für Rückgabe ohne JavaScript.
    """
    form = BarcodeScanForm(request.POST)
    if form.is_valid():
        barcode = form.cleaned_data['barcode']
        service = ReturnService()
        try:
            result = service.process_return(barcode)
            messages.success(request, result.message)
        except InvalidBarcodeException as e:
            messages.error(request, f"Rückgabe abgelehnt: {str(e)}")
        except NoActiveLoanException as e:
            messages.warning(request, f"Rückgabe nicht möglich: {str(e)}")
        except ReturnServiceException as e:
            messages.error(request, f"Systemfehler: {str(e)}")
    return redirect('returns:station')


@api_view(['POST'])
def api_check_return(request):
    """
    Endpoint 1 der Rückgabestation (Annahmeanfrage):
    POST /returns/api/check/
    Payload: {"barcode": "BARCODE-BOOK-001"}
    Prüft, ob das Exemplar physisch von der Station angenommen werden darf.
    """
    barcode = request.data.get('barcode', '').strip()
    if not barcode:
        return Response(
            {"error": "Barcode ist erforderlich."},
            status=status.HTTP_400_BAD_REQUEST
        )

    service = ReturnService()
    try:
        res = service.check_return_eligibility(barcode)
        return Response({
            "eligible": True,
            "barcode": res.barcode,
            "media_title": res.media_title,
            "patron_name": res.patron_name,
            "patron_number": res.patron_number,
            "planned_return_date": res.planned_return_date.isoformat(),
            "is_overdue": res.is_overdue,
            "overdue_days": res.overdue_days,
            "estimated_fee": str(res.estimated_fee),
            "shelf_id": res.shelf_id,
            "compartment": res.compartment,
            "message": res.message,
        }, status=status.HTTP_200_OK)
    except InvalidBarcodeException as e:
        return Response({
            "eligible": False,
            "error_code": "INVALID_BARCODE",
            "message": str(e)
        }, status=status.HTTP_404_NOT_FOUND)
    except NoActiveLoanException as e:
        return Response({
            "eligible": False,
            "error_code": "NO_ACTIVE_LOAN",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            "eligible": False,
            "error_code": "INTERNAL_ERROR",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def api_confirm_return(request):
    """
    Endpoint 2 der Rückgabestation (Rückgabebestätigung):
    POST /returns/api/confirm/
    Payload: {"barcode": "BARCODE-BOOK-001", "return_timestamp": "2026-11-20T10:00:00Z" (optional)}
    Meldet erfolgreiche physische Annahme und schließt den Vorgang auf dem Server ab.
    """
    barcode = request.data.get('barcode', '').strip()
    return_timestamp_str = request.data.get('return_timestamp')

    if not barcode:
        return Response(
            {"error": "Barcode ist erforderlich."},
            status=status.HTTP_400_BAD_REQUEST
        )

    return_timestamp = None
    if return_timestamp_str:
        try:
            return_timestamp = datetime.fromisoformat(return_timestamp_str)
            if timezone.is_naive(return_timestamp):
                return_timestamp = timezone.make_aware(return_timestamp)
        except ValueError:
            return Response(
                {"error": "Ungültiges Datumsformat für 'return_timestamp'. Erwarte ISO 8601."},
                status=status.HTTP_400_BAD_REQUEST
            )

    service = ReturnService()
    try:
        res = service.process_return(barcode, return_timestamp=return_timestamp)
        return Response({
            "success": True,
            "loan_id": res.loan.id,
            "barcode": res.copy.barcode,
            "status": res.copy.status,
            "overdue_days": res.overdue_days,
            "overdue_fee": str(res.overdue_fee),
            "is_withdrawn": res.is_withdrawn,
            "has_pending_reservations": res.has_pending_reservations,
            "shelf_id": res.copy.location.shelf_id,
            "compartment": res.copy.location.compartment,
            "message": res.message,
        }, status=status.HTTP_200_OK)
    except ReturnServiceException as e:
        return Response({
            "success": False,
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
