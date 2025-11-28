"""
URL configuration for geofence_event_processing_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/v1/', include('geofence_app.urls')),
    path('api/v1/vehicles/', include('vehicle_tracking.urls')),
    path('api/v1/zones/', include('zone_management.urls')),
    
    # ArcGIS-based geofencing endpoints
    path('api/v2/', include('geofence_app.arcgis_urls')),
    
    # Taxi-specific API endpoints
    path('api/v2/taxi/', include('geofence_app.taxi_urls')),
    
    # Health checks
    path('health/', include('health_check.urls')),
    
    # Frontend
    # path('', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('', TemplateView.as_view(template_name='us_taxi_dashboard.html'), name='us_taxi_dashboard'),
]
