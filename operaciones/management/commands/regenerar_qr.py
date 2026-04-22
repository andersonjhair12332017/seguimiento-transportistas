from io import BytesIO
import qrcode

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.urls import reverse

from operaciones.models import Transportista


class Command(BaseCommand):
    help = 'Regenera imágenes QR faltantes o desactualizadas para transportistas.'

    def handle(self, *args, **kwargs):
        base_url = getattr(settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000')

        for transportista in Transportista.objects.all():
            url_scan = f"{base_url}{reverse('scan_qr', args=[transportista.qr])}"

            qr_img = qrcode.make(url_scan)
            buffer = BytesIO()
            qr_img.save(buffer, format='PNG')

            transportista.qr_imagen.save(
                f"{transportista.qr}.png",
                ContentFile(buffer.getvalue()),
                save=True
            )

            self.stdout.write(f'QR regenerado para {transportista.placa}')

        self.stdout.write(self.style.SUCCESS('Proceso de regeneración finalizado.'))
