from django import forms

from core.cadastro import validar_cpf_do_formulario
from .models import Assistida, RegistroProntuario, VinculoAtendimento


class RegistroProntuarioForm(forms.ModelForm):
    """Só o texto: autor e assistida vêm do login e da URL, nunca do formulário."""

    class Meta:
        model = RegistroProntuario
        fields = ['texto']


class AssistidaAdminForm(forms.ModelForm):
    class Meta:
        model = Assistida
        fields = '__all__'

    def clean_cpf_assistida(self):
        return validar_cpf_do_formulario(self, 'cpf_assistida', 'cpf_hash')


class VinculoAdminForm(forms.ModelForm):
    class Meta:
        model = VinculoAtendimento
        fields = '__all__'

    def clean(self):
        dados = super().clean()
        assistida, voluntario = dados.get('assistida'), dados.get('voluntario')
        if assistida and voluntario and VinculoAtendimento.objects.filter(
                assistida=assistida, voluntario=voluntario, fim__isnull=True).exists():
            raise forms.ValidationError('Este voluntário já tem vínculo ativo com esta assistida.')
        return dados
