from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from core.cadastro import dados_do_aceite, receber_cadastro, texto
from core.cripto import hash_cpf
from services import apenas_digitos, cpf_valido, formatar_cpf
from .auditoria import registrar
from .forms import RegistroProntuarioForm
from .models import Assistida, RegistroProntuario, RegistroProntuarioVersao
from .permissoes import (
    assistidas_vinculadas, pode_editar_registro, tem_vinculo_ativo, voluntario_de,
)


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


# ----------------------------------------- Páginas internas (só com vínculo)
def _assistida_com_vinculo(request, id_assistida):
    """404 também sem permissão, para não confirmar que a assistida existe."""
    if not tem_vinculo_ativo(request.user, id_assistida):
        registrar(request, 'negacao', id_assistida=id_assistida)
        raise Http404
    return get_object_or_404(Assistida, pk=id_assistida)


@never_cache
@login_required
def lista(request):
    busca = request.GET.get('q', '').strip()
    assistidas = assistidas_vinculadas(request.user).annotate(
        total_registros=Count('registros_prontuario', distinct=True)
    )
    if busca:
        filtro = Q(nome_assistida__icontains=busca) | Q(apelido_assistida__icontains=busca)
        if len(apenas_digitos(busca)) == 11:
            filtro |= Q(cpf_hash=hash_cpf(busca))
        assistidas = assistidas.filter(filtro)
    return render(request, 'assistidas/lista.html', {
        'assistidas': assistidas,
        'busca': busca,
    })


@never_cache
@login_required
def prontuario(request, id_assistida):
    assistida = _assistida_com_vinculo(request, id_assistida)
    registrar(request, 'leitura', id_assistida=assistida.pk)
    registros = assistida.registros_prontuario.select_related(
        'id_autor',
        'id_autor__estagiario',
        'id_autor__advogado',
        'id_autor__bacharel',
    )
    voluntario = voluntario_de(request.user)
    return render(request, 'assistidas/prontuario.html', {
        'assistida': assistida,
        'registros': registros,
        'id_voluntario': voluntario.pk,
    })


@never_cache
@login_required
def novo_registro(request, id_assistida):
    assistida = _assistida_com_vinculo(request, id_assistida)
    form = RegistroProntuarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        registro = form.save(commit=False)
        registro.id_assistida = assistida
        registro.id_autor = voluntario_de(request.user)
        with transaction.atomic():
            registro.save()
            registrar(request, 'criacao', id_assistida=assistida.pk, id_registro=registro.pk)
        return redirect('assistida_prontuario', id_assistida=assistida.pk)
    return render(request, 'assistidas/registro_form.html', {
        'assistida': assistida, 'form': form, 'titulo': 'Novo registro',
    })


@never_cache
@login_required
def editar_registro(request, id_assistida, id_registro):
    assistida = _assistida_com_vinculo(request, id_assistida)
    registro = get_object_or_404(RegistroProntuario, pk=id_registro, id_assistida=assistida)
    if not pode_editar_registro(request.user, registro):
        registrar(request, 'negacao', id_assistida=assistida.pk, id_registro=registro.pk)
        raise Http404

    texto_anterior = registro.texto
    form = RegistroProntuarioForm(request.POST or None, instance=registro)
    if request.method == 'POST' and form.is_valid():
        if form.has_changed():
            with transaction.atomic():
                RegistroProntuarioVersao.objects.create(
                    registro=registro, texto_anterior=texto_anterior, editado_por=request.user)
                form.save()
                registrar(request, 'edicao', id_assistida=assistida.pk, id_registro=registro.pk)
        return redirect('assistida_prontuario', id_assistida=assistida.pk)
    return render(request, 'assistidas/registro_form.html', {
        'assistida': assistida, 'form': form, 'titulo': 'Editar registro',
    })
