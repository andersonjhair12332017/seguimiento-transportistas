from django.urls import path
from . import views

urlpatterns = [
    path("", views.lista, name="lista"),
    path("ingreso/", views.ingreso, name="ingreso"),
    path("scan/<str:codigo_qr>/", views.scan_qr, name="scan_qr"),
    path("historial/<int:pk>/", views.historial, name="historial"),
    path("qr/<str:codigo_qr>.png", views.qr_png, name="qr_png"),

    # Transportistas
    path("transportista/<int:pk>/editar/", views.editar_transportista, name="editar_transportista"),
    path("transportista/<int:pk>/eliminar/", views.eliminar_transportista, name="eliminar_transportista"),

    # Usuarios
    path("usuarios/", views.usuarios_lista, name="usuarios_lista"),
    path("usuarios/crear/", views.usuario_crear, name="usuario_crear"),
    path("usuarios/<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/eliminar/", views.usuario_eliminar, name="usuario_eliminar"),
]