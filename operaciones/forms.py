from django import forms
from django.contrib.auth.models import User, Group
from .models import Transportista, PuertaCargue


class TransportistaIngresoForm(forms.ModelForm):
    class Meta:
        model = Transportista
        fields = ["placa", "conductor", "empresa"]
        widgets = {
            "placa": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: QRY132"
            }),
            "conductor": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nombre del conductor"
            }),
            "empresa": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Empresa transportadora"
            }),
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
        queryset=PuertaCargue.objects.filter(disponible=True),
        widget=forms.Select(attrs={"class": "form-select"})
    )
    complemento = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    observacion = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Observación opcional"
        })
    )


class UsuarioCrearForm(forms.Form):
    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(
        label="Correo",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    grupo = forms.ModelChoiceField(
        label="Grupo / Área",
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    is_active = forms.BooleanField(
        label="Activo",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    is_staff = forms.BooleanField(
        label="Staff",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    is_superuser = forms.BooleanField(
        label="Superusuario",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Ya existe un usuario con ese nombre.")
        return username


class UsuarioEditarForm(forms.Form):
    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(
        label="Correo",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    password = forms.CharField(
        label="Nueva contraseña (opcional)",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    grupo = forms.ModelChoiceField(
        label="Grupo / Área",
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    is_active = forms.BooleanField(
        label="Activo",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    is_staff = forms.BooleanField(
        label="Staff",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    is_superuser = forms.BooleanField(
        label="Superusuario",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )