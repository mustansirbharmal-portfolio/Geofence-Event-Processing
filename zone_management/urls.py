"""
URL configuration for zone_management app.
"""

from django.urls import path
from . import views

app_name = 'zone_management'

urlpatterns = [
    # Zone analytics
    path('<str:zone_id>/analytics/', views.get_zone_analytics, name='get_zone_analytics'),
    path('<str:zone_id>/heatmap/', views.get_zone_heatmap_data, name='get_zone_heatmap_data'),
    
    # Zone management
    path('summary/', views.get_zones_summary, name='get_zones_summary'),
]
