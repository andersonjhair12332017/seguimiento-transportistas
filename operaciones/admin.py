from django.contrib import admin
from .models import Area, Transportista, Movimiento


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'orden')
    ordering = ('orden',)


@admin.register(Transportista)
class TransportistaAdmin(admin.ModelAdmin):
    list_display = ('placa', 'conductor', 'empresa', 'area_actual', 'fecha_ingreso')
    search_fields = ('placa', 'conductor', 'empresa', 'qr')
    list_filter = ('area_actual',)


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('transportista', 'area', 'usuario', 'fecha_hora')
    search_fields = ('transportista__placa', 'transportista__qr', 'usuario__username')
    list_filter = ('area', 'usuario')