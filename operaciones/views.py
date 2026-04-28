from io import BytesIO
from datetime import timedelta
import uuid
import qrcode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    TransportistaIngresoForm,
    TransportistaEditarForm,
    AsignacionCargueForm,
)
from .models import (
    Area,
    Movimiento,
    Transportista,
    PuertaCargue,
    AsignacionCargue,
    RegistroArea,
)

# Umbrales de alerta por área (minutos)
ALERTA_UMBRAL = {
    "PORTERIA": 10,      # visible como Entrada
    "DESPACHOS": 20,
    "PARQUEADERO": 20,
    "CARGUE": 60,
    "FACTURACION": 15,
    "SALIDA": 0,
}


def _obtener_area_usuario(user):
    grupo = user.groups.order_by("name").first()
    if not grupo:
        return None
    return Area.objects.filter(codigo=grupo.name).first()


def _usuario_tiene_area(user, codigo_area):
    area_usuario = _obtener_area_usuario(user)
    return area_usuario is not None and area_usuario.codigo == codigo_area


def _obtener_usuario_sistema():
    usuario, _ = User.objects.get_or_create(
        username="sistema",
        defaults={
            "is_active": False,
            "is_staff": False,
            "is_superuser": False,
        },
    )
    return usuario


def _registrar_movimiento(transportista, area, usuario, tipo="EVENTO"):
    Movimiento.objects.create(
        transportista=transportista,
        area=area,
        usuario=usuario,
        tipo=tipo,
    )


def _obtener_registro_abierto(transportista, codigo_area):
    return (
        RegistroArea.objects.filter(
            transportista=transportista,
            area__codigo=codigo_area,
            activo=True,
        )
        .order_by("-fecha_inicio")
        .first()
    )


def _obtener_cualquier_registro_abierto(transportista):
    return (
        RegistroArea.objects.filter(
            transportista=transportista,
            activo=True,
        )
        .select_related("area")
        .order_by("-fecha_inicio")
        .first()
    )


def _abrir_registro_area(transportista, area, usuario):
    abierto = _obtener_registro_abierto(transportista, area.codigo)
    if abierto:
        return abierto

    return RegistroArea.objects.create(
        transportista=transportista,
        area=area,
        usuario_inicio=usuario,
        activo=True,
    )


def _cerrar_registro_area(transportista, codigo_area, usuario):
    abierto = _obtener_registro_abierto(transportista, codigo_area)
    if abierto:
        abierto.fecha_fin = timezone.now()
        abierto.usuario_fin = usuario
        abierto.activo = False
        abierto.save()
        return abierto
    return None


def _cerrar_registro_area_si_abierto(transportista, codigo_area, usuario):
    return _cerrar_registro_area(transportista, codigo_area, usuario)


def _liberar_puertas_activas(transportista):
    """
    Libera todas las puertas activas del transportista.
    """
    asignaciones_activas = (
        transportista.asignaciones_cargue.filter(activa=True)
        .select_related("puerta")
    )

    for asignacion in asignaciones_activas:
        asignacion.activa = False
        if not asignacion.fecha_fin:
            asignacion.fecha_fin = timezone.now()
        asignacion.save(update_fields=["activa", "fecha_fin"])

        puerta = asignacion.puerta
        if not puerta.disponible:
            puerta.disponible = True
            puerta.save(update_fields=["disponible"])


def _actualizar_parqueadero_transportista(transportista):
    """
    Si el vehículo terminó DESPACHOS y pasan 20 minutos sin iniciar CARGUE,
    lo mueve automáticamente a PARQUEADERO.
    """
    if transportista.esta_finalizado:
        return False

    # Si ya inició cargue alguna vez, no mandarlo a parqueadero
    if transportista.registros_area.filter(area__codigo="CARGUE").exists():
        return False

    ultimo_despacho = (
        transportista.registros_area.filter(area__codigo="DESPACHOS")
        .order_by("-fecha_inicio")
        .first()
    )

    if not ultimo_despacho:
        return False

    # DESPACHOS debe estar cerrado
    if ultimo_despacho.activo or not ultimo_despacho.fecha_fin:
        return False

    # Si ya está en cargue o más allá, no tocar
    if transportista.area_actual.codigo in ["CARGUE", "FACTURACION", "SALIDA"]:
        return False

    if timezone.now() < ultimo_despacho.fecha_fin + timedelta(minutes=20):
        return False

    area_parqueadero = Area.objects.get(codigo="PARQUEADERO")
    usuario_sistema = _obtener_usuario_sistema()

    if transportista.area_actual.codigo == "PARQUEADERO":
        return False

    _abrir_registro_area(transportista, area_parqueadero, usuario_sistema)
    transportista.area_actual = area_parqueadero
    transportista.save(update_fields=["area_actual"])

    _registrar_movimiento(transportista, area_parqueadero, usuario_sistema, "AUTO")
    return True


def _actualizar_parqueadero_automatico():
    transportistas = Transportista.objects.select_related("area_actual").exclude(
        area_actual__codigo="SALIDA"
    )
    for transportista in transportistas:
        _actualizar_parqueadero_transportista(transportista)


def _generar_qr_para_transportista(request, transportista):
    """
    Se mantiene por compatibilidad histórica, pero ya no dependemos del archivo local.
    El QR real se entrega por la vista qr_png().
    """
    # NO-OP intencional para no depender de media local en despliegue
    return None


def qr_png(request, codigo_qr):
    """
    Genera el QR dinámicamente.
    """
    transportista = get_object_or_404(Transportista, qr=codigo_qr)

    base_url = getattr(settings, "PUBLIC_BASE_URL", None)
    if base_url:
        url_scan = f"{base_url}{reverse('scan_qr', args=[transportista.qr])}"
    else:
        url_scan = request.build_absolute_uri(
            reverse("scan_qr", args=[transportista.qr])
        )

    qr_img = qrcode.make(url_scan)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")

    return HttpResponse(buffer.getvalue(), content_type="image/png")


def _tiempo_en_area_minutos(transportista):
    """
    Calcula el tiempo transcurrido en el área actual del vehículo.
    Devuelve minutos.
    """
    codigo = transportista.area_actual.codigo

    # PORTERIA/Entrada: medir desde fecha_ingreso
    if codigo == "PORTERIA":
        delta = timezone.now() - transportista.fecha_ingreso
        return max(0, round(delta.total_seconds() / 60, 2))

    # Registro abierto del área actual
    registro_abierto = (
        RegistroArea.objects.filter(
            transportista=transportista,
            area__codigo=codigo,
            activo=True,
        )
        .order_by("-fecha_inicio")
        .first()
    )

    if registro_abierto:
        delta = timezone.now() - registro_abierto.fecha_inicio
        return max(0, round(delta.total_seconds() / 60, 2))

    # Último registro del área actual
    ultimo_registro = (
        RegistroArea.objects.filter(
            transportista=transportista,
            area__codigo=codigo,
        )
        .order_by("-fecha_inicio")
        .first()
    )

    if ultimo_registro:
        referencia = ultimo_registro.fecha_fin or ultimo_registro.fecha_inicio
        delta = timezone.now() - referencia
        return max(0, round(delta.total_seconds() / 60, 2))

    # Último movimiento del área actual
    ultimo_movimiento = (
        Movimiento.objects.filter(
            transportista=transportista,
            area__codigo=codigo,
        )
        .order_by("-fecha_hora")
        .first()
    )

    if ultimo_movimiento:
        delta = timezone.now() - ultimo_movimiento.fecha_hora
        return max(0, round(delta.total_seconds() / 60, 2))

    # Fallback
    delta = timezone.now() - transportista.fecha_ingreso
    return max(0, round(delta.total_seconds() / 60, 2))


def _formatear_minutos_hhmm(minutos):
    total = max(0, int(round(minutos)))
    horas = total // 60
    mins = total % 60
    return f"{horas:02d} h {mins:02d} min"


def _clase_tiempo(codigo_area, minutos):
    umbral = ALERTA_UMBRAL.get(codigo_area, 15)

    if minutos <= umbral * 0.5:
        return "tiempo-ok", "Normal"
    elif minutos <= umbral:
        return "tiempo-warning", "Atención"
    else:
        return "tiempo-danger", "Alerta"


def _ok(request, transportista, mensaje):
    return render(
        request,
        "operaciones/scan_resultado.html",
        {
            "ok": True,
            "titulo": "Registro correcto",
            "mensaje": mensaje,
            "transportista": transportista,
        },
    )


def _error(request, transportista, mensaje):
    return render(
        request,
        "operaciones/scan_resultado.html",
        {
            "ok": False,
            "titulo": "Registro no permitido",
            "mensaje": mensaje,
            "transportista": transportista,
        },
    )


@login_required
def lista(request):
    _actualizar_parqueadero_automatico()

    q = request.GET.get("q", "").strip()
    vista = request.GET.get("vista", "activos")  # activos | finalizados | puertas

    transportistas = Transportista.objects.select_related("area_actual").all()

    if q:
        transportistas = transportistas.filter(placa__icontains=q)

    activos_qs = transportistas.exclude(area_actual__codigo="SALIDA")
    finalizados_qs = transportistas.filter(area_actual__codigo="SALIDA")

    if vista == "finalizados":
        transportistas = finalizados_qs
    elif vista == "puertas":
        transportistas = activos_qs
    else:
        transportistas = activos_qs

    activos_count = Transportista.objects.exclude(area_actual__codigo="SALIDA").count()
    finalizados_count = Transportista.objects.filter(area_actual__codigo="SALIDA").count()

    areas = Area.objects.all()
    conteos = {
        area.codigo: Transportista.objects.filter(area_actual=area).count()
        for area in areas
    }

    # Tablero de puertas con autocorrección
    tablero_puertas = []
    for puerta in PuertaCargue.objects.all():
        asignacion = (
            puerta.asignaciones.filter(activa=True)
            .select_related("transportista")
            .first()
        )

        if not asignacion and not puerta.disponible:
            puerta.disponible = True
            puerta.save(update_fields=["disponible"])

        if asignacion and not getattr(asignacion, "transportista", None):
            asignacion.activa = False
            if not asignacion.fecha_fin:
                asignacion.fecha_fin = timezone.now()
            asignacion.save(update_fields=["activa", "fecha_fin"])

            puerta.disponible = True
            puerta.save(update_fields=["disponible"])
            asignacion = None

        tablero_puertas.append(
            {
                "numero": puerta.numero,
                "disponible": puerta.disponible if asignacion else True,
                "placa": asignacion.transportista.placa if asignacion else None,
                "complemento": asignacion.complemento if asignacion else False,
            }
        )

    # Indicadores de tiempo y alertas
    alertas_total = 0
    alertas_por_area = {}

    for transportista in activos_qs:
        minutos = _tiempo_en_area_minutos(transportista)
        css, estado = _clase_tiempo(transportista.area_actual.codigo, minutos)

        transportista.tiempo_area_min = minutos
        transportista.tiempo_area_texto = _formatear_minutos_hhmm(minutos)
        transportista.tiempo_css = css
        transportista.tiempo_estado = estado

        if estado == "Alerta":
            alertas_total += 1
            alertas_por_area[transportista.area_actual.codigo] = (
                alertas_por_area.get(transportista.area_actual.codigo, 0) + 1
            )

    # Cuello de botella: área con más vehículos
    cuello_botella_area = None
    cuello_botella_count = 0

    for area in areas:
        count_area = conteos.get(area.codigo, 0)
        if count_area > cuello_botella_count:
            cuello_botella_count = count_area
            cuello_botella_area = area.nombre

    # Área con más alertas
    area_alerta_top = None
    area_alerta_count = 0

    for codigo, total in alertas_por_area.items():
        if total > area_alerta_count:
            area_alerta_count = total
            area_alerta_top = Area.objects.get(codigo=codigo).nombre

    return render(
        request,
        "operaciones/lista.html",
        {
            "transportistas": transportistas,
            "areas": areas,
            "conteos": conteos,
            "area_usuario": _obtener_area_usuario(request.user),
            "q": q,
            "vista": vista,
            "activos_count": activos_count,
            "finalizados_count": finalizados_count,
            "tablero_puertas": tablero_puertas,
            "alertas_total": alertas_total,
            "cuello_botella_area": cuello_botella_area,
            "cuello_botella_count": cuello_botella_count,
            "area_alerta_top": area_alerta_top,
            "area_alerta_count": area_alerta_count,
        },
    )


@login_required
def ingreso(request):
    # Permitir admin o entrada
    if not (request.user.is_superuser or _usuario_tiene_area(request.user, "PORTERIA")):
        return HttpResponseForbidden(
            "Solo el administrador o el personal de Entrada puede registrar ingresos."
        )

    area_entrada = get_object_or_404(Area, codigo="PORTERIA")

    if request.method == "POST":
        form = TransportistaIngresoForm(request.POST)
        if form.is_valid():
            transportista = form.save(commit=False)
            transportista.qr = str(uuid.uuid4())[:8].upper()
            transportista.area_actual = area_entrada
            transportista.save()

            # Registro inicial de entrada
            _abrir_registro_area(transportista, area_entrada, request.user)
            _cerrar_registro_area(transportista, "PORTERIA", request.user)
            _registrar_movimiento(transportista, area_entrada, request.user, "INICIO")

            _generar_qr_para_transportista(request, transportista)

            messages.success(
                request,
                f"Ingreso registrado correctamente para {transportista.placa}.",
            )
            return redirect("lista")
    else:
        form = TransportistaIngresoForm()

    return render(request, "operaciones/ingreso.html", {"form": form})


@login_required
def editar_transportista(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden(
            "Solo el administrador puede editar transportistas."
        )

    transportista = get_object_or_404(Transportista, pk=pk)

    if request.method == "POST":
        form = TransportistaEditarForm(request.POST, instance=transportista)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Transportista {transportista.placa} actualizado correctamente.",
            )
            return redirect("lista")
    else:
        form = TransportistaEditarForm(instance=transportista)

    return render(
        request,
        "operaciones/editar_transportista.html",
        {
            "transportista": transportista,
            "form": form,
        },
    )


@login_required
def eliminar_transportista(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden(
            "Solo el administrador puede eliminar transportistas."
        )

    transportista = get_object_or_404(Transportista, pk=pk)

    if request.method == "POST":
        placa = transportista.placa

        # Liberar puertas activas antes de eliminar
        _liberar_puertas_activas(transportista)

        transportista.delete()
        messages.success(
            request,
            f"Transportista {placa} eliminado correctamente.",
        )
        return redirect("lista")

    return render(
        request,
        "operaciones/eliminar_transportista.html",
        {
            "transportista": transportista,
        },
    )


@login_required
def scan_qr(request, codigo_qr):
    transportista = get_object_or_404(
        Transportista.objects.select_related("area_actual"),
        qr=codigo_qr,
    )

    # Actualización automática de parqueadero si aplica
    _actualizar_parqueadero_transportista(transportista)
    transportista.refresh_from_db()

    area_usuario = _obtener_area_usuario(request.user)
    if area_usuario is None:
        return render(
            request,
            "operaciones/scan_resultado.html",
            {
                "ok": False,
                "titulo": "Usuario sin área asignada",
                "mensaje": "El usuario no pertenece a un grupo/área autorizada.",
                "transportista": transportista,
            },
        )

    codigo_usuario = area_usuario.codigo
    codigo_actual = transportista.area_actual.codigo

    # 🔒 No permitir cambiar de área si hay otra sin finalizar
    registro_abierto = _obtener_cualquier_registro_abierto(transportista)
    if registro_abierto and registro_abierto.area.codigo != codigo_usuario:
        return _error(
            request,
            transportista,
            f'El transportista aún tiene el área "{registro_abierto.area.nombre}" en proceso. Debe escanear nuevamente en esa misma área para finalizar antes de continuar.'
        )

    # ---------------- DESPACHOS ----------------
    if codigo_usuario == "DESPACHOS":
        if codigo_actual == "PORTERIA" and not registro_abierto:
            _abrir_registro_area(transportista, area_usuario, request.user)
            transportista.area_actual = area_usuario
            transportista.save(update_fields=["area_actual"])
            _registrar_movimiento(transportista, area_usuario, request.user, "INICIO")
            return _ok(request, transportista, "Inicio en Despachos registrado correctamente.")

        if codigo_actual == "DESPACHOS" and registro_abierto:
            _cerrar_registro_area(transportista, "DESPACHOS", request.user)
            _registrar_movimiento(transportista, area_usuario, request.user, "FIN")
            return _ok(request, transportista, "Fin en Despachos registrado correctamente.")

        return _error(request, transportista, "Solo puede iniciar Despachos desde Entrada o finalizar si ya está en proceso.")

    # ---------------- PARQUEADERO ----------------
    elif codigo_usuario == "PARQUEADERO":
        return _error(
            request,
            transportista,
            "Parqueadero ya no se registra por escaneo. El sistema lo asigna automáticamente si pasan 20 minutos sin iniciar Cargue."
        )

    # ---------------- CARGUE ----------------
    elif codigo_usuario == "CARGUE":
        asignacion_activa = transportista.asignaciones_cargue.filter(activa=True).first()

        # FIN de cargue
        if codigo_actual == "CARGUE" and registro_abierto and asignacion_activa:
            _liberar_puertas_activas(transportista)
            _cerrar_registro_area(transportista, "CARGUE", request.user)
            _registrar_movimiento(transportista, area_usuario, request.user, "FIN")
            return _ok(request, transportista, "Fin en Cargue registrado correctamente.")

        # INICIO de cargue
        if codigo_actual in ["DESPACHOS", "PARQUEADERO"] and not registro_abierto:
            if request.method == "POST":
                form = AsignacionCargueForm(request.POST)
                if form.is_valid():
                    puerta = form.cleaned_data["puerta"]
                    complemento = form.cleaned_data["complemento"]
                    observacion = form.cleaned_data["observacion"]

                    if not puerta.disponible:
                        return _error(
                            request,
                            transportista,
                            f"La puerta {puerta.numero} ya no está disponible."
                        )

                    _cerrar_registro_area_si_abierto(transportista, "PARQUEADERO", request.user)
                    _abrir_registro_area(transportista, area_usuario, request.user)

                    puerta.disponible = False
                    puerta.save(update_fields=["disponible"])

                    AsignacionCargue.objects.create(
                        transportista=transportista,
                        puerta=puerta,
                        usuario=request.user,
                        complemento=complemento,
                        observacion=observacion,
                        activa=True,
                    )

                    transportista.area_actual = area_usuario
                    transportista.save(update_fields=["area_actual"])

                    _registrar_movimiento(transportista, area_usuario, request.user, "INICIO")

                    return _ok(
                        request,
                        transportista,
                        f"Inicio en Cargue registrado en la puerta {puerta.numero}.",
                    )
            else:
                form = AsignacionCargueForm()

            return render(
                request,
                "operaciones/asignar_cargue.html",
                {
                    "transportista": transportista,
                    "form": form,
                },
            )

        return _error(
            request,
            transportista,
            "No puede iniciar/finalizar Cargue desde el estado actual."
        )

    # ---------------- FACTURACION ----------------
    elif codigo_usuario == "FACTURACION":
        # INICIO facturación
        if codigo_actual == "CARGUE" and not registro_abierto:
            _abrir_registro_area(transportista, area_usuario, request.user)
            transportista.area_actual = area_usuario
            transportista.save(update_fields=["area_actual"])
            _registrar_movimiento(transportista, area_usuario, request.user, "INICIO")
            return _ok(request, transportista, "Inicio en Facturación registrado correctamente.")

        # FIN facturación
        if codigo_actual == "FACTURACION" and registro_abierto:
            _cerrar_registro_area(transportista, "FACTURACION", request.user)
            _registrar_movimiento(transportista, area_usuario, request.user, "FIN")
            return _ok(request, transportista, "Fin en Facturación registrado correctamente.")

        return _error(
            request,
            transportista,
            "Facturación solo puede iniciar después de Cargue o finalizarse si ya está en proceso."
        )

    # ---------------- SALIDA (usuario salida, si existe) ----------------
    elif codigo_usuario == "SALIDA":
        area_salida = Area.objects.get(codigo="SALIDA")

        if codigo_actual == "FACTURACION" and not registro_abierto:
            _abrir_registro_area(transportista, area_salida, request.user)
            _cerrar_registro_area(transportista, "SALIDA", request.user)

            transportista.area_actual = area_salida
            transportista.save(update_fields=["area_actual"])

            _registrar_movimiento(transportista, area_salida, request.user, "FIN")
            return _ok(
                request,
                transportista,
                "Salida registrada correctamente. El vehículo ha finalizado el proceso."
            )

        return _error(
            request,
            transportista,
            "No puede registrar Salida mientras Facturación siga en proceso o si no viene de Facturación."
        )

    # ---------------- ENTRADA/PORTERIA ----------------
    elif codigo_usuario == "PORTERIA":
        area_salida = Area.objects.get(codigo="SALIDA")

        # Entrada puede registrar la salida final si facturación ya terminó
        if codigo_actual == "FACTURACION" and not registro_abierto:
            _abrir_registro_area(transportista, area_salida, request.user)
            _cerrar_registro_area(transportista, "SALIDA", request.user)

            transportista.area_actual = area_salida
            transportista.save(update_fields=["area_actual"])

            _registrar_movimiento(transportista, area_salida, request.user, "FIN")
            return _ok(
                request,
                transportista,
                "Salida registrada correctamente por Entrada. El vehículo ha finalizado el proceso."
            )

        return _error(
            request,
            transportista,
            "Entrada registra el ingreso inicial por formulario y la salida final solo cuando el vehículo ya terminó Facturación."
        )

    return _error(request, transportista, "Área no reconocida.")


@login_required
def historial(request, pk):
    _actualizar_parqueadero_automatico()

    transportista = get_object_or_404(
        Transportista.objects.select_related("area_actual"),
        pk=pk,
    )

    movimientos = transportista.movimientos.select_related("area", "usuario").all()
    registros_area = transportista.registros_area.select_related(
        "area", "usuario_inicio", "usuario_fin"
    ).all()
    asignaciones = transportista.asignaciones_cargue.select_related(
        "puerta", "usuario"
    ).all()

    return render(
        request,
        "operaciones/historial.html",
        {
            "transportista": transportista,
            "movimientos": movimientos,
            "registros_area": registros_area,
            "asignaciones": asignaciones,
        },
    )