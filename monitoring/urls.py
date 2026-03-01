from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.basic_health_check, name='basic_health_check'),
    path('health/services/', views.service_health_check, name='service_health_check'),
]
