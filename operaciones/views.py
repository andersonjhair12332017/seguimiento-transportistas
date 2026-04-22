from io import BytesIO
import uuid
import qrcode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import TransportistaIngresoForm
from .models import Area, Movimiento, Transportista
from django.conf import settings


def _obtener_area_usuario(user):
    """
    Devuelve el objeto Area correspondiente al primer grupo del usuario.
    El nombre del grupo debe ser exactamente:
    PORTERIA, DESPACHOS, PARQUEADERO, CARGUE, FACTURACION, SALIDA
    """
    grupo = user.groups.order_by('name').first()
    if not grupo:
        return None
    return Area.objects.filter(codigo=grupo.name).first()


def _usuario_tiene_area(user, codigo_area):
    area_usuario = _obtener_area_usuario(user)
    return area_usuario is not None and area_usuario.codigo == codigo_area


def _generar_qr_para_transportista(request, transportista):
    """
    Genera un QR con la URL de escaneo accesible desde celular/dispositivos externos.
    """
    base_url = getattr(settings, 'SITE_BASE_URL', None)

    if base_url:
        url_scan = f"{base_url}{reverse('scan_qr', args=[transportista.qr])}"
    else:
        url_scan = request.build_absolute_uri(
            reverse('scan_qr', args=[transportista.qr])
        )

    qr_img = qrcode.make(url_scan)
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')

    nombre_archivo = f"{transportista.qr}.png"
    transportista.qr_imagen.save(
        nombre_archivo,
        ContentFile(buffer.getvalue()),
        save=True
    )


@login_required
def lista(request):
    q = request.GET.get('q', '').strip()

    transportistas = Transportista.objects.select_related('area_actual').all()
    if q:
        transportistas = transportistas.filter(placa__icontains=q)

    areas = Area.objects.all()
    conteos = {
        area.codigo: Transportista.objects.filter(area_actual=area).count()
        for area in areas
    }

    return render(request, 'operaciones/lista.html', {
        'transportistas': transportistas,
        'areas': areas,
        'conteos': conteos,
        'area_usuario': _obtener_area_usuario(request.user),
        'q': q,
    })


@login_required
def ingreso(request):
    # Solo Portería puede registrar ingresos
    if not _usuario_tiene_area(request.user, "PORTERIA"):
        return HttpResponseForbidden("Solo personal de Portería puede registrar ingresos.")

    area_porteria = get_object_or_404(Area, codigo="PORTERIA")

    if request.method == 'POST':
        form = TransportistaIngresoForm(request.POST)
        if form.is_valid():
            transportista = form.save(commit=False)
            transportista.qr = str(uuid.uuid4())[:8].upper()
            transportista.area_actual = area_porteria
            transportista.save()

            # Registrar movimiento inicial con hora exacta y usuario
            Movimiento.objects.create(
                transportista=transportista,
                area=area_porteria,
                usuario=request.user
            )

            # Generar QR
            _generar_qr_para_transportista(request, transportista)

            messages.success(
                request,
                f"Ingreso registrado correctamente para {transportista.placa}."
            )
            return redirect('lista')
    else:
        form = TransportistaIngresoForm()

    return render(request, 'operaciones/ingreso.html', {
        'form': form
    })


@login_required
def scan_qr(request, codigo_qr):
    transportista = get_object_or_404(
        Transportista.objects.select_related('area_actual'),
        qr=codigo_qr
    )

    area_usuario = _obtener_area_usuario(request.user)
    if area_usuario is None:
        return render(request, 'operaciones/scan_resultado.html', {
            'ok': False,
            'titulo': 'Usuario sin área asignada',
            'mensaje': 'El usuario no pertenece a un grupo/área autorizada.',
            'transportista': transportista,
        })

    # Si ya terminó el proceso
    if transportista.finalizado:
        return render(request, 'operaciones/scan_resultado.html', {
            'ok': False,
            'titulo': 'Proceso finalizado',
            'mensaje': 'El transportista ya registró la salida.',
            'transportista': transportista,
        })

    siguiente = transportista.siguiente_area
    if siguiente is None:
        return render(request, 'operaciones/scan_resultado.html', {
            'ok': False,
            'titulo': 'Sin siguiente área',
            'mensaje': 'No existe una siguiente área configurada.',
            'transportista': transportista,
        })

    # Validar que el usuario pertenece exactamente a la siguiente área
    if area_usuario.id != siguiente.id:
        return render(request, 'operaciones/scan_resultado.html', {
            'ok': False,
            'titulo': 'Escaneo no autorizado',
            'mensaje': (
                f'El usuario pertenece a "{area_usuario.nombre}", '
                f'pero la siguiente área esperada es "{siguiente.nombre}".'
            ),
            'transportista': transportista,
        })

    # Registrar el movimiento con fecha/hora exacta y usuario
    Movimiento.objects.create(
        transportista=transportista,
        area=area_usuario,
        usuario=request.user
    )

    # Actualizar estado actual
    transportista.area_actual = area_usuario
    transportista.save(update_fields=['area_actual'])

    return render(request, 'operaciones/scan_resultado.html', {
        'ok': True,
        'titulo': 'Escaneo registrado correctamente',
        'mensaje': (
            f'Se registró el paso de {transportista.placa} '
            f'a la etapa "{area_usuario.nombre}" '
            f'el {Movimiento.objects.filter(transportista=transportista, area=area_usuario).last().fecha_hora|default:""}'
        ),
        'transportista': transportista,
    })

@login_required
def historial(request, pk):
    transportista = get_object_or_404(
        Transportista.objects.select_related('area_actual'),
        pk=pk
    )

    movimientos = transportista.movimientos.select_related('area', 'usuario').all()

    return render(request, 'operaciones/historial.html', {
        'transportista': transportista,
        'movimientos': movimientos,
    })