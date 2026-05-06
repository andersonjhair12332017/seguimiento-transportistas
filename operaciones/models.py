from django.db import models
from django.contrib.auth.models import User

# Se deja SALIDA por compatibilidad histórica con datos antiguos,
# pero el flujo operativo nuevo ya no debe depender de esta área.
AREAS_CONFIG = [
    ("PORTERIA", "Portería", 1),
    ("DESPACHOS", "Despachos", 2),
    ("PARQUEADERO", "Parqueadero", 3),
    ("CARGUE", "Puerta de Cargue", 4),
    ("FACTURACION", "Facturación", 5),
    ("SALIDA", "Salida", 6),
]

AREA_CHOICES = [(codigo, nombre) for codigo, nombre, orden in AREAS_CONFIG]


class Area(models.Model):
    codigo = models.CharField(max_length=30, unique=True, choices=AREA_CHOICES)
    nombre = models.CharField(max_length=50)
    orden = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return self.nombre


class PuertaCargue(models.Model):
    numero = models.PositiveIntegerField(unique=True)
    disponible = models.BooleanField(default=True)

    class Meta:
        ordering = ["numero"]

    def __str__(self):
        return f"Puerta {self.numero}"


class Transportista(models.Model):
    qr = models.CharField(max_length=50, unique=True)
    # Se conserva por compatibilidad histórica
    qr_imagen = models.ImageField(upload_to="qrs/", blank=True, null=True)

    placa = models.CharField(max_length=20)
    conductor = models.CharField(max_length=100)
    empresa = models.CharField(max_length=100)

    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    fecha_salida = models.DateTimeField(null=True, blank=True)

    area_actual = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="transportistas_actuales"
    )

    class Meta:
        ordering = ["-fecha_ingreso"]

    def __str__(self):
        return f"{self.placa} - {self.conductor}"

    @property
    def esta_finalizado(self):
        return self.fecha_salida is not None

    @property
    def siguiente_area_texto(self):
        codigo = self.area_actual.codigo

        if self.esta_finalizado:
            return "Salida"

        if codigo == "PORTERIA":
            return "Despachos"
        elif codigo == "DESPACHOS":
            return "Puerta de Cargue (o Parqueadero automático a los 20 min)"
        elif codigo == "PARQUEADERO":
            return "Puerta de Cargue"
        elif codigo == "CARGUE":
            return "Facturación"
        elif codigo == "FACTURACION":
            # El vehículo finaliza en Portería
            return "Portería"
        elif codigo == "SALIDA":
            # Compatibilidad histórica
            return "Salida"
        return "-"

    @property
    def puertas_actuales(self):
        return self.asignaciones_cargue.filter(
            activa=True
        ).select_related("puerta")


class Movimiento(models.Model):
    transportista = models.ForeignKey(
        Transportista,
        on_delete=models.CASCADE,
        related_name="movimientos"
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="movimientos"
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="movimientos_realizados"
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=20, default="EVENTO")  # INICIO / FIN / AUTO / EVENTO

    class Meta:
        ordering = ["fecha_hora"]

    def __str__(self):
        return f"{self.transportista.placa} - {self.area.nombre} - {self.fecha_hora:%Y-%m-%d %H:%M:%S}"


class RegistroArea(models.Model):
    transportista = models.ForeignKey(
        Transportista,
        on_delete=models.CASCADE,
        related_name="registros_area"
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="registros_area"
    )
    usuario_inicio = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="registros_inicio_area"
    )
    usuario_fin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="registros_fin_area",
        blank=True,
        null=True
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"{self.transportista.placa} - {self.area.nombre}"

    @property
    def duracion_minutos(self):
        if self.fecha_fin:
            delta = self.fecha_fin - self.fecha_inicio
            return round(delta.total_seconds() / 60, 2)
        return None


class AsignacionCargue(models.Model):
    transportista = models.ForeignKey(
        Transportista,
        on_delete=models.CASCADE,
        related_name="asignaciones_cargue"
    )
    puerta = models.ForeignKey(
        PuertaCargue,
        on_delete=models.PROTECT,
        related_name="asignaciones"
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="asignaciones_cargue_realizadas"
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    complemento = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)
    observacion = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-fecha_inicio"]

    def __str__(self):
        tipo = "Complemento" if self.complemento else "Cargue"
        return f"{self.transportista.placa} - {self.puerta} - {tipo}"