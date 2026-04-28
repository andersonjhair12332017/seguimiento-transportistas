from django import forms
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
