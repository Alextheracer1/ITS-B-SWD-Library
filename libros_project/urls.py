"""
Root URL configuration for LiBros project.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    
    # Routen für die 3 Use Cases:
    path('loans/', include('apps.loans.urls', namespace='loans')),
    path('returns/', include('apps.returns.urls', namespace='returns')),
    path('reservations/', include('apps.reservations.urls', namespace='reservations')),
]
