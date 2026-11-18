"""
URL-Routing für Use Case 3: Medium reservieren
Verantwortlich: Marcel Kitzmantel (3. Autor)
"""

from django.urls import path
from apps.reservations import views

app_name = 'reservations'

urlpatterns = [
    path('', views.reservation_index_view, name='index'),
    path('create/', views.reservation_create_view, name='create'),
    path('<int:reservation_id>/cancel/', views.reservation_cancel_view, name='cancel'),
    path('api/create/', views.api_create_reservation, name='api_create'),
    path('api/cancel/', views.api_cancel_reservation, name='api_cancel'),
    path('api/check/', views.api_check_capacity, name='api_check'),
]
