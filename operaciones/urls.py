from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista, name='lista'),
    path('ingreso/', views.ingreso, name='ingreso'),
    path('scan/<str:codigo_qr>/', views.scan_qr, name='scan_qr'),
    path('historial/<int:pk>/', views.historial, name='historial'),
]