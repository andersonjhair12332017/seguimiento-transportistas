from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group


class Command(BaseCommand):
    help = "Crea o actualiza los usuarios operativos por área."

    def handle(self, *args, **kwargs):
        usuarios = [
            ("porteria1", "Porteria.123", "PORTERIA"),
            ("despachos1", "Despachos.123", "DESPACHOS"),
            ("parqueadero1", "Parqueadero.123", "PARQUEADERO"),
            ("cargue1", "Cargue.123", "CARGUE"),
            ("facturacion1", "Facturacion.123", "FACTURACION"),
            ("salida1", "Salida.123", "SALIDA"),
        ]

        for username, password, grupo_nombre in usuarios:
            user, created = User.objects.get_or_create(username=username)
            user.is_active = True
            user.set_password(password)
            user.save()

            grupo, _ = Group.objects.get_or_create(name=grupo_nombre)
            user.groups.clear()
            user.groups.add(grupo)

            estado = "creado" if created else "actualizado"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuario {username} {estado} correctamente -> {grupo_nombre}"
                )
            )

        self.stdout.write(self.style.SUCCESS("Proceso finalizado."))