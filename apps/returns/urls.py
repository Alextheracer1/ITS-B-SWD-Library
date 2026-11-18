"""
URL-Routing für Use Case 2: Medium zurückgeben (Return Station)
Verantwortlich: David Leberbauer (2. Autor)
"""

from django.urls import path
from apps.returns import views

app_name = 'returns'

urlpatterns = [
    path('', views.return_station_view, name='station'),
    path('process/', views.process_return_web, name='process_web'),
    path('api/check/', views.api_check_return, name='api_check'),
    path('api/confirm/', views.api_confirm_return, name='api_confirm'),
]
