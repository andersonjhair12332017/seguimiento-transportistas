from io import BytesIO
from datetime import timedelta, time as dt_time
import uuid
import qrcode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    TransportistaIngresoForm,
    TransportistaEditarForm,
    AsignacionCargueForm,
    UsuarioCrearForm,
    UsuarioEditarForm,
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
    "PORTERIA": 10,
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
    if transportista.esta_finalizado:
        return False

    if transportista.registros_area.filter(area__codigo="CARGUE").exists():
        return False

    ultimo_despacho = (
        transportista.registros_area.filter(area__codigo="DESPACHOS")
        .order_by("-fecha_inicio")
        .first()
    )

    if not ultimo_despacho:
        return False

    if ultimo_despacho.activo or not ultimo_despacho.fecha_fin:
        return False

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
    return None


def qr_png(request, codigo_qr):
    transportista = get_object_or_404(Transportista, qr=codigo_qr)

    base_url = getattr(settings, "PUBLIC_BASE_URL", None)
    if base_url:
        url_scan = f"{base_url}{reverse('scan_qr', args=[transportista.qr])}"
    else:
        url_scan = request.build_absolute_uri(reverse("scan_qr", args=[transportista.qr]))

    qr_img = qrcode.make(url_scan)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")

    return HttpResponse(buffer.getvalue(), content_type="image/png")


def _tiempo_en_area_minutos(transportista):
    codigo = transportista.area_actual.codigo

    if codigo == "PORTERIA":
        delta = timezone.now() - transportista.fecha_ingreso
        return max(0, round(delta.total_seconds() / 60, 2))

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

    delta = timezone.now() - transportista.fecha_ingreso
    return max(0, round(delta.total_seconds() / 60, 2))


def _formatear_minutos_hhmm(minutos):
    total = max(0, int(round(minutos)))
    horas = total // 60
    mins = total % 60
    return f"{horas:02d} h {mins:02d} min"


def _formatear_segundos_hhmmss(segundos):
    total = max(0, int(segundos))
    horas = total // 3600
    mins = (total % 3600) // 60
    secs = total % 60
    return f"{horas:02d} h {mins:02d} min {secs:02d} s"


def _clase_tiempo(codigo_area, minutos):
    umbral = ALERTA_UMBRAL.get(codigo_area, 15)

    if minutos <= umbral * 0.5:
        return "tiempo-ok", "Normal", "fila-ok"
    elif minutos <= umbral:
        return "tiempo-warning", "Atención", "fila-warning"
    else:
        return "tiempo-danger", "Alerta", "fila-danger"


def _ok(request, transportista, mensaje):
    area_usuario = _obtener_area_usuario(request.user)
    return render(
        request,
        "operaciones/scan_resultado.html",
        {
            "ok": True,
            "titulo": "Registro correcto",
            "mensaje": mensaje,
            "transportista": transportista,
            "area_usuario": area_usuario,
        },
    )


def _error(request, transportista, mensaje):
    area_usuario = _obtener_area_usuario(request.user)
    return render(
        request,
        "operaciones/scan_resultado.html",
        {
            "ok": False,
            "titulo": "Registro no permitido",
            "mensaje": mensaje,
            "transportista": transportista,
            "area_usuario": area_usuario,
        },
    )


def _obtener_turno_desde_hora(hora_valor):
    """
    Día   -> 06:00:01 a 17:59:59
    Noche -> 18:00:00 a 06:00:00
    """
    if hora_valor >= dt_time(18, 0, 0) or hora_valor <= dt_time(6, 0, 0):
        return "noche"
    return "día"


def _marcar_estado_transportista(transportista, panel_render_epoch):
    minutos = _tiempo_en_area_minutos(transportista)
    css, estado, fila_css = _clase_tiempo(transportista.area_actual.codigo, minutos)

    registro_abierto = _obtener_cualquier_registro_abierto(transportista)

    transportista.tiempo_area_min = minutos
    transportista.tiempo_area_segundos = int(round(minutos * 60))
    transportista.tiempo_area_texto = _formatear_minutos_hhmm(minutos)
    transportista.tiempo_css = css
    transportista.tiempo_estado = estado
    transportista.fila_css = fila_css
    transportista.panel_render_epoch = panel_render_epoch
    transportista.pendiente_cierre = bool(
        registro_abierto and registro_abierto.area.codigo == transportista.area_actual.codigo
    )
    transportista.area_pendiente_nombre = registro_abierto.area.nombre if registro_abierto else None
    return transportista


def _construir_contexto_lista(request):
    _actualizar_parqueadero_automatico()

    q = request.GET.get("q", "").strip()
    vista = request.GET.get("vista", "activos")
    panel_render_epoch = int(timezone.now().timestamp())

    transportistas_base = Transportista.objects.select_related("area_actual").all()

    if q:
        transportistas_base = transportistas_base.filter(
            Q(placa__icontains=q) |
            Q(conductor__icontains=q) |
            Q(empresa__icontains=q)
        )

    activos_qs = list(transportistas_base.exclude(area_actual__codigo="SALIDA"))
    finalizados_qs = list(transportistas_base.filter(area_actual__codigo="SALIDA"))

    for t in activos_qs:
        _marcar_estado_transportista(t, panel_render_epoch)

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

    alertas_total = 0
    alertas_por_area = {}
    pendientes_cierre_total = 0

    for transportista in activos_qs:
        if transportista.tiempo_estado == "Alerta":
            alertas_total += 1
            alertas_por_area[transportista.area_actual.codigo] = (
                alertas_por_area.get(transportista.area_actual.codigo, 0) + 1
            )
        if transportista.pendiente_cierre:
            pendientes_cierre_total += 1

    cuello_botella_area = None
    cuello_botella_count = 0
    for area in areas:
        count_area = conteos.get(area.codigo, 0)
        if count_area > cuello_botella_count:
            cuello_botella_count = count_area
            cuello_botella_area = area.nombre

    area_alerta_top = None
    area_alerta_count = 0
    for codigo, total in alertas_por_area.items():
        if total > area_alerta_count:
            area_alerta_count = total
            area_alerta_top = Area.objects.get(codigo=codigo).nombre

    top_demoras = sorted(
        activos_qs,
        key=lambda x: x.tiempo_area_min,
        reverse=True
    )[:5]

    total_segundos_activos = sum(t.tiempo_area_segundos for t in activos_qs) if activos_qs else 0
    promedio_segundos_activos = int(total_segundos_activos / len(activos_qs)) if activos_qs else 0

    turno_actual = _obtener_turno_desde_hora(timezone.localtime().time())

    return {
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
        "pendientes_cierre_total": pendientes_cierre_total,
        "cuello_botella_area": cuello_botella_area,
        "cuello_botella_count": cuello_botella_count,
        "area_alerta_top": area_alerta_top,
        "area_alerta_count": area_alerta_count,
        "top_demoras": top_demoras,
        "kpi_promedio_texto": _formatear_segundos_hhmmss(promedio_segundos_activos),
        "kpi_total_texto": _formatear_segundos_hhmmss(total_segundos_activos),
        "turno_actual": turno_actual,
        "panel_render_epoch": panel_render_epoch,
    }


@login_required
def lista(request):
    context = _construir_contexto_lista(request)

    if request.GET.get("partial") == "1" or request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "operaciones/_lista_panel.html", context)

    return render(request, "operaciones/lista.html", context)


@login_required
def supervisor(request):
    if not request.user.is_superuser:
        messages.error(request, "Solo el administrador puede acceder a la vista supervisor.")
        return redirect("lista")

    context = _construir_contexto_lista(request)

    if request.GET.get("partial") == "1" or request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "operaciones/_supervisor_panel.html", context)

    return render(request, "operaciones/supervisor.html", context)


@login_required
def historial_global(request):
    fecha = request.GET.get("fecha")
    turno = request.GET.get("turno", "")
    area_codigo = request.GET.get("area", "")
    q = request.GET.get("q", "").strip()

    if fecha:
        try:
            fecha_base = timezone.datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            fecha_base = timezone.localdate()
    else:
        fecha_base = timezone.localdate()

    registros = RegistroArea.objects.select_related(
        "transportista", "area", "usuario_inicio", "usuario_fin"
    ).filter(fecha_inicio__date=fecha_base)

    if area_codigo:
        registros = registros.filter(area__codigo=area_codigo)

    if q:
        registros = registros.filter(
            Q(transportista__placa__icontains=q) |
            Q(transportista__conductor__icontains=q) |
            Q(transportista__empresa__icontains=q)
        )

    lista_registros = []
    for r in registros.order_by("-fecha_inicio"):
        hora_local = timezone.localtime(r.fecha_inicio).time()
        r.turno_texto = _obtener_turno_desde_hora(hora_local)

        if turno and r.turno_texto != turno:
            continue

        lista_registros.append(r)

    areas = Area.objects.all()

    return render(
        request,
        "operaciones/historial_global.html",
        {
            "registros": lista_registros,
            "areas": areas,
            "fecha": fecha_base.strftime("%Y-%m-%d"),
            "turno": turno,
            "area_codigo": area_codigo,
            "q": q,
        },
    )


@login_required
def resolver_codigo_manual(request):
    if request.method != "POST":
        return redirect("pantalla_escaneo")

    codigo = request.POST.get("codigo", "").strip()
    if not codigo:
        messages.error(request, "Debes ingresar un código QR o una placa.")
        return redirect("pantalla_escaneo")

    transportista = Transportista.objects.filter(qr__iexact=codigo).first()

    if not transportista:
        transportista = Transportista.objects.filter(placa__iexact=codigo).first()

    if not transportista:
        messages.error(request, f"No se encontró un transportista con código/placa: {codigo}")
        return redirect("pantalla_escaneo")

    return redirect("scan_qr", codigo_qr=transportista.qr)


@login_required
def pantalla_escaneo(request):
    area_usuario = _obtener_area_usuario(request.user)

    if area_usuario is None and not request.user.is_superuser:
        messages.error(request, "Tu usuario no tiene un área asignada para operar el escaneo.")
        return redirect("lista")

    placa = request.GET.get("placa", "").strip()
    nombre = request.GET.get("nombre", "").strip()
    registro_inicio = request.GET.get("registro_inicio", "").strip()
    registro_fin = request.GET.get("registro_fin", "").strip()

    ultimos_registros = RegistroArea.objects.select_related(
        "transportista", "area", "usuario_inicio", "usuario_fin"
    ).filter(
        Q(usuario_inicio=request.user) | Q(usuario_fin=request.user)
    )

    if placa:
        ultimos_registros = ultimos_registros.filter(
            transportista__placa__icontains=placa
        )

    if nombre:
        ultimos_registros = ultimos_registros.filter(
            transportista__conductor__icontains=nombre
        )

    if registro_inicio:
        try:
            fecha_ini = timezone.datetime.strptime(registro_inicio, "%Y-%m-%d").date()
            ultimos_registros = ultimos_registros.filter(fecha_inicio__date__gte=fecha_ini)
        except ValueError:
            pass

    if registro_fin:
        try:
            fecha_fin = timezone.datetime.strptime(registro_fin, "%Y-%m-%d").date()
            ultimos_registros = ultimos_registros.filter(fecha_fin__date__lte=fecha_fin)
        except ValueError:
            pass

    ultimos_registros = ultimos_registros.order_by("-fecha_inicio")[:30]

    return render(
        request,
        "operaciones/pantalla_escaneo.html",
        {
            "area_usuario": area_usuario,
            "ultimos_registros": ultimos_registros,
            "placa_filtro": placa,
            "nombre_filtro": nombre,
            "registro_inicio_filtro": registro_inicio,
            "registro_fin_filtro": registro_fin,
        },
    )


@login_required
def ingreso(request):
    if not (request.user.is_superuser or _usuario_tiene_area(request.user, "PORTERIA")):
        messages.error(request, "Solo el administrador o el personal de Entrada puede registrar ingresos.")
        return redirect("lista")

    area_entrada = get_object_or_404(Area, codigo="PORTERIA")

    if request.method == "POST":
        form = TransportistaIngresoForm(request.POST)
        if form.is_valid():
            transportista = form.save(commit=False)
            transportista.qr = str(uuid.uuid4())[:8].upper()
            transportista.area_actual = area_entrada
            transportista.save()

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
        messages.error(request, "Solo el administrador puede editar transportistas.")
        return redirect("lista")

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
        messages.error(request, "Solo el administrador puede eliminar transportistas.")
        return redirect("lista")

    transportista = get_object_or_404(Transportista, pk=pk)

    if request.method == "POST":
        placa = transportista.placa

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
                "area_usuario": None,
            },
        )

    codigo_usuario = area_usuario.codigo
    codigo_actual = transportista.area_actual.codigo

    registro_abierto = _obtener_cualquier_registro_abierto(transportista)
    if registro_abierto and registro_abierto.area.codigo != codigo_usuario:
        return _error(
            request,
            transportista,
            f'El transportista aún tiene el área "{registro_abierto.area.nombre}" en proceso. Debe escanear nuevamente en esa misma área para finalizar antes de continuar.'
        )

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

    elif codigo_usuario == "PARQUEADERO":
        return _error(
            request,
            transportista,
            "Parqueadero ya no se registra por escaneo. El sistema lo asigna automáticamente si pasan 20 minutos sin iniciar Cargue."
        )

    elif codigo_usuario == "CARGUE":
        asignacion_activa = transportista.asignaciones_cargue.filter(activa=True).first()

        if codigo_actual == "CARGUE" and registro_abierto and asignacion_activa:
            _liberar_puertas_activas(transportista)
            _cerrar_registro_area(transportista, "CARGUE", request.user)
            _registrar_movimiento(transportista, area_usuario, request.user, "FIN")
            return _ok(request, transportista, "Fin en Cargue registrado correctamente.")

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

    elif codigo_usuario == "FACTURACION":
        if codigo_actual == "CARGUE" and not registro_abierto:
            _abrir_registro_area(transportista, area_usuario, request.user)
            transportista.area_actual = area_usuario
            transportista.save(update_fields=["area_actual"])
            _registrar_movimiento(transportista, area_usuario, request.user, "INICIO")
            return _ok(request, transportista, "Inicio en Facturación registrado correctamente.")

        if codigo_actual == "FACTURACION" and registro_abierto:
            _cerrar_registro_area(transportista, "FACTURACION", request.user)
            _registrar_movimiento(transportista, area_usuario, request.user, "FIN")
            return _ok(request, transportista, "Fin en Facturación registrado correctamente.")

        return _error(
            request,
            transportista,
            "Facturación solo puede iniciar después de Cargue o finalizarse si ya está en proceso."
        )

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

    elif codigo_usuario == "PORTERIA":
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


@login_required
def usuarios_lista(request):
    if not request.user.is_superuser:
        messages.error(request, "Solo el administrador puede administrar usuarios.")
        return redirect("lista")

    usuarios = User.objects.all().order_by("username").prefetch_related("groups")

    return render(
        request,
        "operaciones/usuarios_lista.html",
        {
            "usuarios": usuarios,
        },
    )


@login_required
def usuario_crear(request):
    if not request.user.is_superuser:
        messages.error(request, "Solo el administrador puede crear usuarios.")
        return redirect("lista")

    if request.method == "POST":
        form = UsuarioCrearForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )

            user.is_active = form.cleaned_data["is_active"]
            user.is_staff = form.cleaned_data["is_staff"] or form.cleaned_data["is_superuser"]
            user.is_superuser = form.cleaned_data["is_superuser"]
            user.save()

            grupo = form.cleaned_data["grupo"]
            user.groups.clear()
            if grupo:
                user.groups.add(grupo)

            messages.success(request, f"Usuario {user.username} creado correctamente.")
            return redirect("usuarios_lista")
    else:
        form = UsuarioCrearForm()

    return render(
        request,
        "operaciones/usuario_form.html",
        {
            "form": form,
            "titulo": "Crear usuario",
            "boton": "Crear usuario",
        },
    )


@login_required
def usuario_editar(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Solo el administrador puede editar usuarios.")
        return redirect("lista")

    usuario_obj = get_object_or_404(User, pk=pk)
    grupo_actual = usuario_obj.groups.first()

    if request.method == "POST":
        form = UsuarioEditarForm(request.POST)
        if form.is_valid():
            nuevo_username = form.cleaned_data["username"].strip()

            if User.objects.exclude(pk=usuario_obj.pk).filter(username=nuevo_username).exists():
                form.add_error("username", "Ya existe otro usuario con ese nombre.")
            else:
                usuario_obj.username = nuevo_username
                usuario_obj.email = form.cleaned_data["email"]
                usuario_obj.is_active = form.cleaned_data["is_active"]
                usuario_obj.is_staff = form.cleaned_data["is_staff"] or form.cleaned_data["is_superuser"]
                usuario_obj.is_superuser = form.cleaned_data["is_superuser"]

                nueva_password = form.cleaned_data["password"]
                if nueva_password:
                    usuario_obj.set_password(nueva_password)

                usuario_obj.save()

                grupo = form.cleaned_data["grupo"]
                usuario_obj.groups.clear()
                if grupo:
                    usuario_obj.groups.add(grupo)

                messages.success(request, f"Usuario {usuario_obj.username} actualizado correctamente.")
                return redirect("usuarios_lista")
    else:
        form = UsuarioEditarForm(
            initial={
                "username": usuario_obj.username,
                "email": usuario_obj.email,
                "grupo": grupo_actual,
                "is_active": usuario_obj.is_active,
                "is_staff": usuario_obj.is_staff,
                "is_superuser": usuario_obj.is_superuser,
            }
        )

    return render(
        request,
        "operaciones/usuario_form.html",
        {
            "form": form,
            "titulo": f"Editar usuario: {usuario_obj.username}",
            "boton": "Guardar cambios",
        },
    )


@login_required
def usuario_eliminar(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Solo el administrador puede eliminar usuarios.")
        return redirect("lista")

    usuario_obj = get_object_or_404(User, pk=pk)

    if usuario_obj == request.user:
        messages.error(request, "No puedes eliminar tu propio usuario mientras estás autenticado.")
        return redirect("usuarios_lista")

    if usuario_obj.username == "sistema":
        messages.error(request, "No se puede eliminar el usuario del sistema.")
        return redirect("usuarios_lista")

    if request.method == "POST":
        username = usuario_obj.username
        usuario_obj.delete()
        messages.success(request, f"Usuario {username} eliminado correctamente.")
        return redirect("usuarios_lista")

    return render(
        request,
        "operaciones/usuario_eliminar.html",
        {
            "usuario_obj": usuario_obj,
        },
    )