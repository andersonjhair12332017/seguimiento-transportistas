import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Crea o actualiza el superusuario remoto usando variables de entorno."

    def handle(self, *args, **kwargs):
        username = os.getenv("ADMIN_USERNAME")
        password = os.getenv("ADMIN_PASSWORD")
        email = os.getenv("ADMIN_EMAIL", "")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "ADMIN_USERNAME o ADMIN_PASSWORD no definidos. Se omite creación de superusuario."
                )
            )
            return

        user, created = User.objects.get_or_create(username=username)

        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        estado = "creado" if created else "actualizado"

        self.stdout.write(
            self.style.SUCCESS(
                f"Superusuario {username} {estado} correctamente."
            )
        )