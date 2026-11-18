"""
URL-Routing für Use Case 1: Medium ausleihen
Verantwortlich: Alexander Graf (1. Autor)
"""

from django.urls import path
from apps.loans import views

app_name = 'loans'

urlpatterns = [
    path('', views.loan_catalog_view, name='catalog'),
    path('checkout/', views.loan_checkout_view, name='checkout'),
    path('api/checkout/', views.api_loan_checkout, name='api_checkout'),
]
