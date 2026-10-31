from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from core.cadastro import dados_do_aceite, receber_cadastro, texto
from services import apenas_digitos, cpf_valido, formatar_cpf
from .models import Assistida


# ---------------------------------------------------------------- API pública
CAMPOS_PUBLICOS = (
    'cpf', 'nome', 'cep', 'idade', 'apelido', 'cidade', 'estado', 'rua', 'num_endereco',
    'complementoEndereco', 'telefone', 'pode_deixar_recado', 'melhor_horario',
)


def _salvar_assistida(data):
    cpf = texto(data, 'cpf')
    cep = apenas_digitos(texto(data, 'cep'))
    telefone = apenas_digitos(texto(data, 'telefone'))

    erros = {}
    if not cpf_valido(cpf):
        erros['cpf'] = 'CPF inválido.'
    if len(cep) != 8:
        erros['cep'] = 'CEP inválido.'
    if len(telefone) not in (10, 11):
        erros['telefone'] = 'Informe o telefone com DDD.'
    if erros:
        raise ValidationError(erros)

    assistida = Assistida(
        cpf_assistida=formatar_cpf(cpf),
        nome_assistida=texto(data, 'nome'),
        cep_assistida=cep,
        idade_assistida=data.get('idade'),
        apelido_assistida=texto(data, 'apelido'),
        cidade_assistida=texto(data, 'cidade'),
        estado_assistida=texto(data, 'estado'),
        rua_assistida=texto(data, 'rua'),
        num_endereco_assistida=texto(data, 'num_endereco'),
        complemento_endereco_assistida=texto(data, 'complementoEndereco'),
        telefone_assistida=telefone,
        pode_deixar_recado=data.get('pode_deixar_recado') is True,
        melhor_horario=texto(data, 'melhor_horario'),
        **dados_do_aceite(),
    )
    # A unicidade fica a cargo do banco, para cair na pendência sem revelar nada.
    assistida.full_clean(validate_unique=False)
    assistida.save()


def adicionar(request):
    return receber_cadastro(request, 'assistida', _salvar_assistida, CAMPOS_PUBLICOS)


# ------------------------------------------- Páginas internas (só equipe/staff)
@never_cache
@staff_member_required
def lista(request):
    busca = request.GET.get('q', '').strip()
    assistidas = Assistida.objects.annotate(
        total_registros=Count('registros_prontuario')
    )
    if busca:
        assistidas = assistidas.filter(
            Q(nome_assistida__icontains=busca)
            | Q(cpf_assistida__icontains=busca)
            | Q(apelido_assistida__icontains=busca)
        )
    return render(request, 'assistidas/lista.html', {
        'assistidas': assistidas,
        'busca': busca,
    })


@never_cache
@staff_member_required
def prontuario(request, id_assistida):
    assistida = get_object_or_404(Assistida, pk=id_assistida)
    registros = assistida.registros_prontuario.select_related(
        'id_autor',
        'id_autor__estagiario',
        'id_autor__advogado',
        'id_autor__bacharel',
    )
    return render(request, 'assistidas/prontuario.html', {
        'assistida': assistida,
        'registros': registros,
    })
