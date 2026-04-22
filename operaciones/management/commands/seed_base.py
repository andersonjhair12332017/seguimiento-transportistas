from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from operaciones.models import Area, AREAS_CONFIG


class Command(BaseCommand):
    help = 'Crea áreas base y grupos de seguridad por área.'

    def handle(self, *args, **kwargs):
        for codigo, nombre, orden in AREAS_CONFIG:
            area, created = Area.objects.get_or_create(
                codigo=codigo,
                defaults={'nombre': nombre, 'orden': orden}
            )
            if not created:
                area.nombre = nombre
                area.orden = orden
                area.save()

            Group.objects.get_or_create(name=codigo)

        self.stdout.write(self.style.SUCCESS('Áreas y grupos creados/actualizados correctamente.'))