from django.core.exceptions import ValidationError

from core.cadastro import dados_do_aceite, receber_cadastro, texto
from services import cpf_valido, formatar_cpf
from .models import Advogado, Bacharel, Estagiario, Voluntario

CAMPOS_COMUNS = (
    'email', 'nome', 'dataNascimento', 'sexo', 'cidade', 'estado', 'endereco',
    'telefone', 'instagram', 'cpf', 'rg',
)


def _salvar_voluntario(data):
    cpf = texto(data, 'cpf')
    if not cpf_valido(cpf):
        raise ValidationError({'cpf': 'CPF inválido.'})

    voluntario = Voluntario(
        email_voluntario=texto(data, 'email'),
        nomecompleto_voluntario=texto(data, 'nome'),
        datanasc_voluntario=texto(data, 'dataNascimento'),
        sexo_voluntario=texto(data, 'sexo'),
        cidade_voluntario=texto(data, 'cidade'),
        estado_voluntario=texto(data, 'estado'),
        endereco_voluntario=texto(data, 'endereco'),
        telefone_voluntario=texto(data, 'telefone'),
        instagram_voluntario=texto(data, 'instagram'),
        cpf_voluntario=formatar_cpf(cpf),
        rg_voluntario=texto(data, 'rg'),
        **dados_do_aceite(),
    )
    # A unicidade fica a cargo do banco, para cair na pendência sem revelar nada.
    voluntario.full_clean(validate_unique=False)
    voluntario.save()
    return voluntario


def _salvar_com_subtipo(montar):
    """Grava o voluntário e o subtipo; receber_cadastro desfaz tudo se um falhar."""
    def salvar(data):
        subtipo = montar(_salvar_voluntario(data), data)
        subtipo.full_clean(validate_unique=False)
        subtipo.save()
    return salvar


def _estagiario(voluntario, data):
    return Estagiario(
        id_voluntario=voluntario,
        curso_estagiario=texto(data, 'curso'),
        periodo_estagiario=texto(data, 'periodo'),
    )


def _advogado(voluntario, data):
    return Advogado(id_voluntario=voluntario, oab_advogado=texto(data, 'oab'))


def _bacharel(voluntario, data):
    return Bacharel(id_voluntario=voluntario, cursoformacao_bacharel=texto(data, 'cursoBacharel'))


def adicionar_estagiario(request):
    return receber_cadastro(
        request, 'estagiario', _salvar_com_subtipo(_estagiario), CAMPOS_COMUNS + ('curso', 'periodo'))


def adicionar_advogado(request):
    return receber_cadastro(
        request, 'advogado', _salvar_com_subtipo(_advogado), CAMPOS_COMUNS + ('oab',))


def adicionar_bacharel(request):
    return receber_cadastro(
        request, 'bacharel', _salvar_com_subtipo(_bacharel), CAMPOS_COMUNS + ('cursoBacharel',))
