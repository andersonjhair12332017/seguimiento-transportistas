from io import BytesIO
import qrcode

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from operaciones.models import Transportista


class Command(BaseCommand):
    help = 'Regenera imágenes QR para todos los transportistas usando la URL pública actual.'

    def handle(self, *args, **kwargs):
        base_url = getattr(settings, 'PUBLIC_BASE_URL', None)

        if not base_url:
            self.stdout.write(self.style.ERROR(
                "No existe PUBLIC_BASE_URL en settings.py"
            ))
            return

        for transportista in Transportista.objects.all():
            url_scan = f"{base_url}{reverse('scan_qr', args=[transportista.qr])}"

            qr_img = qrcode.make(url_scan)
            buffer = BytesIO()
            qr_img.save(buffer, format='PNG')

            # Eliminar QR anterior si existe
            if transportista.qr_imagen:
                transportista.qr_imagen.delete(save=False)

            nombre_archivo = f"{transportista.qr}_{timezone.now().strftime('%Y%m%d%H%M%S')}.png"

            transportista.qr_imagen.save(
                nombre_archivo,
                ContentFile(buffer.getvalue()),
                save=True
            )

            self.stdout.write(f'QR regenerado para {transportista.placa}')

        self.stdout.write(self.style.SUCCESS('Proceso finalizado.'))
