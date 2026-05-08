from django import forms
from django.contrib.auth.models import Group

from .models import (
    Transportista,
    PuertaCargue,
    CausalNovedadCargue,
)


class TransportistaIngresoForm(forms.ModelForm):
    class Meta:
        model = Transportista
        fields = ["placa", "conductor", "empresa"]
        widgets = {
            "placa": forms.TextInput(attrs={"class": "form-control"}),
            "conductor": forms.TextInput(attrs={"class": "form-control"}),
            "empresa": forms.TextInput(attrs={"class": "form-control"}),
        }


class TransportistaEditarForm(forms.ModelForm):
    class Meta:
        model = Transportista
        fields = ["placa", "conductor", "empresa"]
        widgets = {
            "placa": forms.TextInput(attrs={"class": "form-control"}),
            "conductor": forms.TextInput(attrs={"class": "form-control"}),
            "empresa": forms.TextInput(attrs={"class": "form-control"}),
        }


class AsignacionCargueForm(forms.Form):
    puerta = forms.ModelChoiceField(
        queryset=PuertaCargue.objects.none(),
        label="Puerta de cargue",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    complemento = forms.BooleanField(
        required=False,
        label="¿Es cargue complementario?"
    )
    cubicaje = forms.DecimalField(
        required=True,
        max_digits=8,
        decimal_places=2,
        min_value=0,
        label="Cubicaje del vehículo (m³)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    observacion = forms.CharField(
        required=False,
        max_length=255,
        label="Observación",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["puerta"].queryset = PuertaCargue.objects.filter(disponible=True).order_by("numero")


class CierreCargueForm(forms.Form):
    cargue_completo = forms.ChoiceField(
        choices=[
            ("si", "Sí, se terminó de cargar completamente"),
            ("no", "No, vuelve a parqueadero para complemento"),
        ],
        widget=forms.RadioSelect,
        label="Resultado del cargue",
    )
    observacion = forms.CharField(
        required=False,
        max_length=255,
        label="Observación",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class NovedadCargueForm(forms.Form):
    causal = forms.ModelChoiceField(
        queryset=CausalNovedadCargue.objects.filter(activa=True).order_by("nombre"),
        label="Causal de novedad",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    observacion = forms.CharField(
        required=False,
        max_length=255,
        label="Observación",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class CausalNovedadCargueForm(forms.ModelForm):
    class Meta:
        model = CausalNovedadCargue
        fields = ["nombre", "descripcion", "activa"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class UsuarioCrearForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Usuario",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=False,
        label="Correo",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    grupo = forms.ModelChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        label="Grupo / Área",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_active = forms.BooleanField(required=False, initial=True, label="Activo")
    is_staff = forms.BooleanField(required=False, label="Staff")
    is_superuser = forms.BooleanField(required=False, label="Superusuario")


class UsuarioEditarForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Usuario",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=False,
        label="Correo",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    password = forms.CharField(
        required=False,
        label="Nueva contraseña (opcional)",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    grupo = forms.ModelChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        label="Grupo / Área",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_active = forms.BooleanField(required=False, label="Activo")
    is_staff = forms.BooleanField(required=False, label="Staff")
    is_superuser = forms.BooleanField(required=False, label="Superusuario")
