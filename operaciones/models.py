from django.db import models
from django.contrib.auth.models import User

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


class Transportista(models.Model):
    qr = models.CharField(max_length=50, unique=True)
    qr_imagen = models.ImageField(upload_to='qrs/', blank=True, null=True)
    placa = models.CharField(max_length=20)
    conductor = models.CharField(max_length=100)
    empresa = models.CharField(max_length=100)

    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    area_actual = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name='transportistas_actuales'
    )

    class Meta:
        ordering = ['-fecha_ingreso']

    def __str__(self):
        return f"{self.placa} - {self.conductor}"

    @property
    def siguiente_area(self):
        return Area.objects.filter(orden=self.area_actual.orden + 1).first()

    @property
    def finalizado(self):
        return self.area_actual.codigo == "SALIDA"


class Movimiento(models.Model):
    transportista = models.ForeignKey(
        Transportista,
        on_delete=models.CASCADE,
        related_name='movimientos'
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name='movimientos'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='movimientos_realizados'
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_hora']

    def __str__(self):
        return f"{self.transportista.placa} - {self.area.nombre} - {self.fecha_hora:%Y-%m-%d %H:%M:%S}"