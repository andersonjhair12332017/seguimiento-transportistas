from django.urls import path
from . import views

try:
    from . import qr_print_views
    TIENE_QR_PRINT = True
except Exception:
    TIENE_QR_PRINT = False

urlpatterns = [
    path("", views.lista, name="lista"),
    path("ingreso/", views.ingreso, name="ingreso"),
    path("scan/<str:codigo_qr>/", views.scan_qr, name="scan_qr"),
    path("resolver-codigo/", views.resolver_codigo_manual, name="resolver_codigo_manual"),

    path("historial/<int:pk>/", views.historial, name="historial"),
    path("historial/registros/", views.historial_global, name="historial_global"),

    path("supervisor/", views.supervisor, name="supervisor"),
    path("escanear/", views.pantalla_escaneo, name="pantalla_escaneo"),

    path("qr/<str:codigo_qr>.png", views.qr_png, name="qr_png"),

    # Transportistas
    path("transportista/<int:pk>/editar/", views.editar_transportista, name="editar_transportista"),
    path("transportista/<int:pk>/eliminar/", views.eliminar_transportista, name="eliminar_transportista"),
    path("transportista/<int:pk>/novedad-cargue/", views.registrar_novedad_cargue, name="registrar_novedad_cargue"),

    # Causales de novedad
    path("causales-novedad/", views.causales_novedad_lista, name="causales_novedad_lista"),
    path("causales-novedad/crear/", views.causal_novedad_crear, name="causal_novedad_crear"),
    path("causales-novedad/<int:pk>/editar/", views.causal_novedad_editar, name="causal_novedad_editar"),
    path("causales-novedad/<int:pk>/eliminar/", views.causal_novedad_eliminar, name="causal_novedad_eliminar"),

    # Usuarios
    path("usuarios/", views.usuarios_lista, name="usuarios_lista"),
    path("usuarios/crear/", views.usuario_crear, name="usuario_crear"),
    path("usuarios/<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/eliminar/", views.usuario_eliminar, name="usuario_eliminar"),
]

if TIENE_QR_PRINT:
    urlpatterns += [
        path("qr/imprimir/<str:codigo_qr>/", qr_print_views.qr_imprimir, name="qr_imprimir"),
    ]