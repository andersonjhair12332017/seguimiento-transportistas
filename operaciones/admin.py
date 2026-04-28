from django.contrib import admin
from .models import Area, PuertaCargue, Transportista, Movimiento, RegistroArea, AsignacionCargue


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "orden")


@admin.register(PuertaCargue)
class PuertaCargueAdmin(admin.ModelAdmin):
    list_display = ("numero", "disponible")
    list_editable = ("disponible",)


@admin.register(Transportista)
class TransportistaAdmin(admin.ModelAdmin):
    list_display = ("placa", "conductor", "empresa", "area_actual", "fecha_ingreso")
    search_fields = ("placa", "conductor", "empresa", "qr")
    list_filter = ("area_actual",)


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ("transportista", "area", "tipo", "usuario", "fecha_hora")


@admin.register(RegistroArea)
class RegistroAreaAdmin(admin.ModelAdmin):
    list_display = (
        "transportista", "area",
        "fecha_inicio", "fecha_fin",
        "usuario_inicio", "usuario_fin",
        "activo"
    )


@admin.register(AsignacionCargue)
class AsignacionCargueAdmin(admin.ModelAdmin):
    list_display = (
        "transportista", "puerta", "complemento",
        "fecha_inicio", "fecha_fin",
        "activa", "usuario"
    )