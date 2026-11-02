import re
import secrets
import unicodedata

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from assistidas.forms import AssistidaAdminForm
from assistidas.models import PREFIXO_ANONIMIZADA, Assistida
from assistidas.permissoes import GRUPO_ATENDIMENTO, GRUPO_COORDENACAO
from atendimentos.models import Atendimento
from core.cadastro import validar_cpf_do_formulario
from core.models import ContaInterna
from services import apenas_digitos
from voluntarios.models import Advogado, Bacharel, Estagiario, Voluntario

FUNCOES = [
    ('psicologia', 'Psicólogo(a)'),
    ('advogado', 'Advogado(a)'),
    ('servico_social', 'Assistente social'),
    ('estagiario', 'Estagiário(a)'),
    ('outra', 'Outra formação'),
]
CURSO_DA_FUNCAO = {'psicologia': 'Psicologia', 'servico_social': 'Serviço Social'}


def senha_temporaria():
    return secrets.token_urlsafe(9)


def _login_livre(email):
    base = unicodedata.normalize('NFKD', email.split('@')[0]).encode('ascii', 'ignore').decode()
    base = re.sub(r'[^a-z0-9._-]', '', base.lower())[:140] or 'usuario'
    candidato, numero = base, 1
    Usuario = get_user_model()
    while Usuario.objects.filter(username=candidato).exists():
        numero += 1
        candidato = f'{base}{numero}'
    return candidato


def criar_acesso(voluntario, coordenacao=False):
    """Cria o login da pessoa e devolve a senha temporária, mostrada uma única vez."""
    senha = senha_temporaria()
    usuario = get_user_model().objects.create_user(
        _login_livre(voluntario.email_voluntario), voluntario.email_voluntario, senha,
        first_name=voluntario.nomecompleto_voluntario.split(' ')[0][:150])
    ContaInterna.objects.create(usuario=usuario, trocar_senha=True)
    usuario.groups.add(Group.objects.get(name=GRUPO_ATENDIMENTO))
    if coordenacao:
        definir_coordenacao(usuario, True)
    voluntario.usuario = usuario
    voluntario.save()
    return usuario, senha


def definir_coordenacao(usuario, ativa):
    grupo = Group.objects.get(name=GRUPO_COORDENACAO)
    if ativa:
        usuario.groups.add(grupo)
    else:
        usuario.groups.remove(grupo)
    usuario.is_staff = ativa
    usuario.save(update_fields=['is_staff'])


class PessoaForm(forms.ModelForm):
    # Maior que a coluna de propósito: aceita a máscara, que sai em clean_telefone_voluntario.
    telefone_voluntario = forms.CharField(label='Telefone com DDD', max_length=20)

    class Meta:
        model = Voluntario
        fields = [
            'nomecompleto_voluntario', 'email_voluntario', 'telefone_voluntario', 'datanasc_voluntario',
            'sexo_voluntario', 'cpf_voluntario', 'rg_voluntario', 'endereco_voluntario',
            'cidade_voluntario', 'estado_voluntario',
        ]
        labels = {
            'nomecompleto_voluntario': 'Nome completo',
            'email_voluntario': 'E-mail',
            'telefone_voluntario': 'Telefone com DDD',
            'datanasc_voluntario': 'Data de nascimento',
            'sexo_voluntario': 'Sexo',
            'cpf_voluntario': 'CPF',
            'rg_voluntario': 'RG',
            'endereco_voluntario': 'Endereço',
            'cidade_voluntario': 'Cidade',
            'estado_voluntario': 'UF',
        }
        widgets = {'datanasc_voluntario': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def clean_cpf_voluntario(self):
        return validar_cpf_do_formulario(self, 'cpf_voluntario', 'cpf_hash_voluntario')

    def clean_telefone_voluntario(self):
        telefone = self.cleaned_data['telefone_voluntario']
        if 'telefone_voluntario' not in self.changed_data:
            return telefone
        digitos = apenas_digitos(telefone)
        if len(digitos) not in (10, 11):
            raise forms.ValidationError('Informe o telefone com DDD.')
        return digitos

    def clean_estado_voluntario(self):
        return self.cleaned_data['estado_voluntario'].upper()


class EditarPessoaForm(PessoaForm):
    class Meta(PessoaForm.Meta):
        fields = PessoaForm.Meta.fields + [
            'instagram_voluntario', 'cpfupload_voluntario', 'fotoupload_voluntario', 'termoupload_voluntario',
        ]
        labels = {
            **PessoaForm.Meta.labels,
            'instagram_voluntario': 'Instagram',
            'cpfupload_voluntario': 'Cópia do CPF recebida',
            'fotoupload_voluntario': 'Foto recebida',
            'termoupload_voluntario': 'Termo assinado recebido',
        }


class AdicionarPessoaForm(PessoaForm):
    """Um formulário só: dados, função e login nascem juntos."""
    funcao = forms.ChoiceField(label='Função', choices=FUNCOES, widget=forms.RadioSelect)
    oab = forms.CharField(label='Número da OAB', max_length=9, required=False)
    curso = forms.CharField(label='Curso ou formação', max_length=20, required=False)
    periodo = forms.ChoiceField(
        label='Período', choices=[('', 'Escolha')] + Estagiario.PERIODOS, required=False)
    coordenacao = forms.BooleanField(label='Também pode usar este painel (coordenação)', required=False)

    field_order = ['funcao', 'oab', 'curso', 'periodo'] + PessoaForm.Meta.fields + ['coordenacao']

    def __init__(self, *args, para_mim=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.para_mim = para_mim
        if para_mim:
            del self.fields['coordenacao']

    def clean(self):
        dados = super().clean()
        funcao = dados.get('funcao')
        if funcao == 'advogado':
            if not dados.get('oab'):
                self.add_error('oab', 'Informe o número da OAB.')
            elif Advogado.objects.filter(oab_advogado=dados['oab']).exists():
                self.add_error('oab', 'Esta OAB já está cadastrada.')
        if funcao in ('estagiario', 'outra') and not dados.get('curso'):
            self.add_error('curso', 'Informe o curso.')
        if funcao == 'estagiario' and not dados.get('periodo'):
            self.add_error('periodo', 'Escolha o período.')
        return dados

    @transaction.atomic
    def salvar(self, usuario_atual=None):
        """Com `usuario_atual`, usa esse login. Sem ele, cria login e senha temporária."""
        voluntario = self.save()
        dados = self.cleaned_data
        funcao = dados['funcao']
        if funcao == 'advogado':
            Advogado.objects.create(id_voluntario=voluntario, oab_advogado=dados['oab'])
        elif funcao == 'estagiario':
            Estagiario.objects.create(
                id_voluntario=voluntario, curso_estagiario=dados['curso'], periodo_estagiario=dados['periodo'])
        else:
            Bacharel.objects.create(
                id_voluntario=voluntario,
                cursoformacao_bacharel=CURSO_DA_FUNCAO.get(funcao, dados['curso']))

        if usuario_atual is not None:
            voluntario.usuario = usuario_atual
            voluntario.save()
            usuario_atual.groups.add(Group.objects.get(name=GRUPO_ATENDIMENTO))
            return voluntario, usuario_atual, None
        usuario, senha = criar_acesso(voluntario, dados.get('coordenacao', False))
        return voluntario, usuario, senha


class AssistidaPainelForm(AssistidaAdminForm):
    class Meta(AssistidaAdminForm.Meta):
        fields = [
            'nome_assistida', 'apelido_assistida', 'cpf_assistida', 'idade_assistida', 'telefone_assistida',
            'pode_deixar_recado', 'melhor_horario', 'cep_assistida', 'rua_assistida',
            'num_endereco_assistida', 'complemento_endereco_assistida', 'cidade_assistida', 'estado_assistida',
        ]
        labels = {
            'nome_assistida': 'Nome completo',
            'apelido_assistida': 'Como prefere ser chamada',
            'cpf_assistida': 'CPF',
            'idade_assistida': 'Idade',
            'cep_assistida': 'CEP',
            'rua_assistida': 'Rua',
            'complemento_endereco_assistida': 'Complemento',
            'cidade_assistida': 'Cidade',
            'estado_assistida': 'UF',
        }


class EscolherAtendenteForm(forms.Form):
    voluntario = forms.ModelChoiceField(
        queryset=Voluntario.objects.none(), label='Quem vai atender', empty_label='Escolha uma pessoa')

    def __init__(self, *args, assistida, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['voluntario'].queryset = Voluntario.objects.filter(
            usuario__is_active=True,
        ).exclude(
            pk__in=assistida.vinculos.filter(fim__isnull=True).values('voluntario'),
        ).select_related('estagiario', 'advogado', 'bacharel').order_by('nomecompleto_voluntario')
        self.fields['voluntario'].label_from_instance = lambda v: f'{v.nomecompleto_voluntario} ({v.funcao})'


class AtendimentoForm(forms.ModelForm):
    class Meta:
        model = Atendimento
        fields = ['id_assistida', 'id_estagiario', 'data_atendimento', 'hora_atendimento']
        labels = {
            'id_assistida': 'Assistida',
            'id_estagiario': 'Estagiário(a)',
            'data_atendimento': 'Data',
            'hora_atendimento': 'Horário',
        }
        widgets = {
            'data_atendimento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'hora_atendimento': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_assistida'].queryset = Assistida.objects.exclude(
            cpf_hash__startswith=PREFIXO_ANONIMIZADA)
        self.fields['id_estagiario'].queryset = Estagiario.objects.select_related('id_voluntario')
