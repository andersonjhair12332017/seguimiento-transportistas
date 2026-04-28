from django.urls import path
from . import views

urlpatterns = [
    path("", views.lista, name="lista"),
    path("ingreso/", views.ingreso, name="ingreso"),
    path("scan/<str:codigo_qr>/", views.scan_qr, name="scan_qr"),
    path("historial/<int:pk>/", views.historial, name="historial"),

    # QR dinámico
    path("qr/<str:codigo_qr>.png", views.qr_png, name="qr_png"),

    # Editar / eliminar
    path("transportista/<int:pk>/editar/", views.editar_transportista, name="editar_transportista"),
    path("transportista/<int:pk>/eliminar/", views.eliminar_transportista, name="eliminar_transportista"),
]