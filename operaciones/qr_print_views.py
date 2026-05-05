from django.shortcuts import get_object_or_404, render
from .models import Transportista


def qr_imprimir(request, codigo_qr):
    transportista = get_object_or_404(Transportista, qr=codigo_qr)
    return render(
        request,
        "operaciones/qr_imprimir.html",
        {
            "transportista": transportista,
        },
    )