from django import forms
from .models import Transportista


class TransportistaIngresoForm(forms.ModelForm):
    class Meta:
        model = Transportista
        fields = ['placa', 'conductor', 'empresa']
        widgets = {
            'placa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: QRY132'
            }),
            'conductor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del conductor'
            }),
            'empresa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Empresa transportadora'
            }),
        }
