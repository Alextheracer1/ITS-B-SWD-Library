"""
Use Case 1: Medium ausleihen (Loan)
API & Controller Layer: Web & Kiosk Controller (Django Views)
Interface: IPatronWebAPI
Verantwortlich: Alexander Graf (1. Autor)

Aufgaben:
- Mediensuche & Anzeige der Verfügbarkeit
- Entgegennahme der Ausleihanfrage vom Web/Kiosk-Client
- Aufruf des Loan Services
- Fehlerbehandlung (FSK-Fehler, keine Exemplare frei, Concurrency-Konflikt)
- Rückgabe der Bestätigung inkl. Standort (Regal-ID, Fach)
"""

from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from apps.core.models import Media, Patron, Copy, Reservation
from apps.core.repositories import MasterDataRepository
from apps.loans.forms import LoanRequestForm
from apps.loans.loan_service import (
    LoanService,
    LoanServiceException,
    FSKViolationException,
    UnavailableMediaException
)


def loan_catalog_view(request):
    """
    Übersicht aller Medien inkl. Verfügbarkeitsanzeige und Ausleihmöglichkeit.
    """
    search_query = request.GET.get('q', '').strip()
    media_list = MasterDataRepository.list_all_media(search_query if search_query else None)
    
    # Für jedes Medium freie Exemplare und Standorte sammeln
    media_data = []
    for m in media_list:
        available_copies = m.copies.filter(status=Copy.STATUS_AVAILABLE)
        total_copies = m.copies.count()
        locations = {f"Regal {c.location.shelf_id}, Fach {c.location.compartment}" for c in available_copies}
        
        media_data.append({
            'media': m,
            'available_count': available_copies.count(),
            'total_count': total_copies,
            'locations': list(locations),
            'genres': list(m.genres.all())
        })

    patrons = Patron.objects.all()
    form = LoanRequestForm()

    context = {
        'media_data': media_data,
        'patrons': patrons,
        'search_query': search_query,
        'form': form,
    }
    return render(request, 'loans/loan_form.html', context)


@require_http_methods(["POST"])
def loan_checkout_view(request):
    """
    Führt die Ausleihe über das HTML-Formular aus.
    """
    form = LoanRequestForm(request.POST)
    loan_result = None

    if form.is_valid():
        patron = form.cleaned_data['patron']
        media = form.cleaned_data['media']
        reservation = form.cleaned_data['reservation']

        service = LoanService()
        try:
            loan_result = service.borrow_media(
                patron_id=patron.id,
                media_id=media.id,
                reservation_id=reservation.id if reservation else None
            )
            messages.success(request, loan_result.message)
            return render(request, 'loans/loan_form.html', {
                'success_result': loan_result,
                'media_data': [],
                'patrons': Patron.objects.all(),
                'form': LoanRequestForm(),
            })
        except FSKViolationException as e:
            messages.error(request, f"FSK-Fehler: {str(e)}")
        except UnavailableMediaException as e:
            messages.warning(request, f"Verfügbarkeitsfehler: {str(e)}")
        except LoanServiceException as e:
            messages.error(request, f"Fehler bei Ausleihe: {str(e)}")
        except Exception as e:
            messages.error(request, f"Unerwarteter Systemfehler: {str(e)}")

    # Bei Fehler zurück zur Katalogseite
    return redirect('loans:catalog')


@api_view(['POST'])
def api_loan_checkout(request):
    """
    REST-API Endpoint für dezentrale Kiosks und Web-Clients:
    POST /loans/api/checkout/
    Payload: {"patron_id": 1, "media_id": 2, "reservation_id": 3 (optional)}
    """
    patron_id = request.data.get('patron_id')
    media_id = request.data.get('media_id')
    reservation_id = request.data.get('reservation_id')

    if not patron_id or not media_id:
        return Response(
            {"error": "Die Felder 'patron_id' und 'media_id' sind erforderlich."},
            status=status.HTTP_400_BAD_REQUEST
        )

    service = LoanService()
    try:
        result = service.borrow_media(
            patron_id=int(patron_id),
            media_id=int(media_id),
            reservation_id=int(reservation_id) if reservation_id else None
        )
        return Response({
            "success": True,
            "message": result.message,
            "loan_id": result.loan.id,
            "barcode": result.copy.barcode,
            "shelf_id": result.shelf_id,
            "compartment": result.compartment,
            "planned_return_date": result.loan.planned_return_date.isoformat(),
        }, status=status.HTTP_201_CREATED)
    except FSKViolationException as e:
        return Response({"error": "FSK_VIOLATION", "message": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except UnavailableMediaException as e:
        return Response({"error": "NOT_AVAILABLE", "message": str(e)}, status=status.HTTP_409_CONFLICT)
    except LoanServiceException as e:
        return Response({"error": "LOAN_ERROR", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
