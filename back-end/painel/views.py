from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from assistidas import direitos
from assistidas.auditoria import registrar
from assistidas.models import (
    PREFIXO_ANONIMIZADA, Assistida, PendenciaCadastro, RegistroAcesso, VinculoAtendimento,
)
from assistidas.permissoes import (
    GRUPO_COORDENACAO, e_coordenacao, pode_usar_painel, tem_vinculo_ativo, voluntario_de,
)
from atendimentos.models import Atendimento
from core.cripto import hash_cpf
from core.models import ContaInterna
from services import apenas_digitos
from voluntarios.models import Voluntario
from .forms import (
    AdicionarPessoaForm, AssistidaPainelForm, AtendimentoForm, EditarPessoaForm, EscolherAtendenteForm,
    criar_acesso, definir_coordenacao, senha_temporaria,
)


def painel_required(view):
    """404 para quem não é da coordenação, como no restante da área interna."""
    @wraps(view)
    def interna(request, *args, **kwargs):
        if not pode_usar_painel(request.user):
            raise Http404
        return view(request, *args, **kwargs)
    return never_cache(login_required(interna))


def _ativas():
    return Assistida.objects.exclude(cpf_hash__startswith=PREFIXO_ANONIMIZADA)


def _com_atendentes(assistidas):
    return assistidas.annotate(total_atendentes=Count('vinculos', filter=Q(vinculos__fim__isnull=True)))


def _pagina(request, consulta, por_pagina=25):
    return Paginator(consulta, por_pagina).get_page(request.GET.get('pagina'))


@painel_required
def inicio(request):
    return render(request, 'painel/inicio.html', {
        'sem_atendente': _com_atendentes(_ativas()).filter(total_atendentes=0).count(),
        'pendencias': PendenciaCadastro.objects.filter(resolvida_em__isnull=True).count(),
        'sem_acesso': Voluntario.objects.filter(usuario__isnull=True).count(),
        'proximos': Atendimento.objects.filter(data_atendimento__gte=timezone.localdate()).count(),
        'eu_atendo': voluntario_de(request.user) is not None,
    })


# ------------------------------------------------------------------ assistidas
@painel_required
def assistidas(request):
    busca = request.GET.get('q', '').strip()
    so_sem_atendente = request.GET.get('filtro') == 'sem_atendente'
    consulta = _com_atendentes(Assistida.objects.all())
    if busca:
        filtro = Q(nome_assistida__icontains=busca) | Q(apelido_assistida__icontains=busca)
        if len(apenas_digitos(busca)) == 11:
            filtro |= Q(cpf_hash=hash_cpf(busca))
        consulta = consulta.filter(filtro)
    if so_sem_atendente:
        consulta = consulta.filter(total_atendentes=0).exclude(cpf_hash__startswith=PREFIXO_ANONIMIZADA)
    return render(request, 'painel/assistidas.html', {
        'pagina': _pagina(request, consulta), 'busca': busca, 'so_sem_atendente': so_sem_atendente,
    })


@painel_required
def assistida_nova(request):
    form = AssistidaPainelForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        assistida = form.save()
        messages.success(request, 'Assistida cadastrada. Agora escolha quem vai atendê-la.')
        return redirect('painel_assistida', assistida.pk)
    return render(request, 'painel/formulario.html', {
        'form': form, 'titulo': 'Nova assistida', 'voltar': reverse('painel_assistidas'),
    })


@painel_required
def assistida(request, id_assistida):
    alvo = get_object_or_404(Assistida, pk=id_assistida)
    vinculos = alvo.vinculos.filter(fim__isnull=True).select_related(
        'voluntario', 'voluntario__estagiario', 'voluntario__advogado', 'voluntario__bacharel')
    meu = voluntario_de(request.user)
    return render(request, 'painel/assistida.html', {
        'assistida': alvo,
        'vinculos': vinculos,
        'form': EscolherAtendenteForm(assistida=alvo),
        'meu_voluntario': meu,
        'ja_atendo': tem_vinculo_ativo(request.user, alvo.pk),
    })


@painel_required
def assistida_editar(request, id_assistida):
    alvo = get_object_or_404(_ativas(), pk=id_assistida)
    form = AssistidaPainelForm(request.POST or None, instance=alvo)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
            registrar(request, 'cadastro_alterado', id_assistida=alvo.pk)
        messages.success(request, 'Cadastro atualizado.')
        return redirect('painel_assistida', alvo.pk)
    return render(request, 'painel/formulario.html', {
        'form': form, 'titulo': f'Editar {alvo.nome_assistida}',
        'voltar': reverse('painel_assistida', args=[alvo.pk]),
    })


@painel_required
@require_POST
def atendente_adicionar(request, id_assistida):
    alvo = get_object_or_404(_ativas(), pk=id_assistida)
    form = EscolherAtendenteForm(request.POST, assistida=alvo)
    if not form.is_valid():
        messages.error(request, 'Escolha uma pessoa da lista.')
        return redirect('painel_assistida', alvo.pk)
    voluntario = form.cleaned_data['voluntario']
    try:
        with transaction.atomic():
            VinculoAtendimento.objects.create(assistida=alvo, voluntario=voluntario, designado_por=request.user)
            registrar(request, 'vinculo_criado', id_assistida=alvo.pk)
    except IntegrityError:
        messages.error(request, 'Esta pessoa já atende esta assistida.')
    else:
        messages.success(request, f'{voluntario.nomecompleto_voluntario} agora atende esta assistida.')
    return redirect('painel_assistida', alvo.pk)


@painel_required
@require_POST
def atendente_encerrar(request, id_assistida, id_vinculo):
    vinculo = get_object_or_404(
        VinculoAtendimento, pk=id_vinculo, assistida_id=id_assistida, fim__isnull=True)
    with transaction.atomic():
        vinculo.fim = timezone.now()
        vinculo.save()
        registrar(request, 'vinculo_encerrado', id_assistida=id_assistida)
    messages.success(request, 'Atendimento encerrado. O acesso ao prontuário foi retirado.')
    return redirect('painel_assistida', id_assistida)


DIREITOS = {
    'exportar': {
        'titulo': 'Exportar dados',
        'aviso': 'Gera um arquivo com os dados da assistida. O prontuário só entra se você a atende. '
                 'A exportação fica registrada.',
        'botao': 'Baixar arquivo',
    },
    'anonimizar': {
        'titulo': 'Anonimizar',
        'aviso': 'Apaga dados pessoais e prontuário e encerra os atendimentos. Ficam só idade e UF. '
                 'Isso não pode ser desfeito.',
        'botao': 'Anonimizar',
    },
    'excluir': {
        'titulo': 'Excluir definitivamente',
        'aviso': 'Apaga cadastro, prontuário, vínculos e atendimentos. Isso não pode ser desfeito.',
        'botao': 'Excluir definitivamente',
    },
}


@painel_required
def assistida_direito(request, id_assistida, acao):
    if acao not in DIREITOS:
        raise Http404
    alvo = get_object_or_404(_ativas(), pk=id_assistida)
    if request.method != 'POST':
        return render(request, 'painel/confirmar.html', {**DIREITOS[acao], 'assistida': alvo})
    if acao == 'exportar':
        resposta = JsonResponse(
            direitos.dados_para_exportar(request, alvo), json_dumps_params={'ensure_ascii': False, 'indent': 2})
        resposta['Content-Disposition'] = f'attachment; filename="assistida-{alvo.pk}.json"'
        add_never_cache_headers(resposta)
        return resposta
    if acao == 'anonimizar':
        direitos.anonimizar(request, alvo)
        messages.success(request, 'Assistida anonimizada.')
        return redirect('painel_assistida', alvo.pk)
    direitos.excluir(request, alvo)
    messages.success(request, 'Assistida excluída.')
    return redirect('painel_assistidas')


# ------------------------------------------------------------------ equipe
@painel_required
def equipe(request):
    busca = request.GET.get('q', '').strip()
    consulta = Voluntario.objects.select_related(
        'usuario', 'estagiario', 'advogado', 'bacharel',
    ).annotate(
        total_assistidas=Count('vinculos', filter=Q(vinculos__fim__isnull=True)),
    ).order_by('nomecompleto_voluntario')
    if not request.user.is_superuser:
        consulta = consulta.exclude(usuario__is_superuser=True)
    if busca:
        consulta = consulta.filter(nomecompleto_voluntario__icontains=busca)
    return render(request, 'painel/equipe.html', {
        'pagina': _pagina(request, consulta), 'busca': busca,
        'eu_atendo': voluntario_de(request.user) is not None,
    })


def _adicionar(request, para_mim):
    form = AdicionarPessoaForm(request.POST or None, para_mim=para_mim)
    if request.method == 'POST' and form.is_valid():
        voluntario, usuario, senha = form.salvar(request.user if para_mim else None)
        registrar(request, 'usuario_vinculado')
        if senha is None:
            messages.success(request, 'Pronto! Agora escolha, na página da assistida, quem você vai atender.')
            return redirect('painel_assistidas')
        return render(request, 'painel/acesso_criado.html', {
            'voluntario': voluntario, 'usuario': usuario, 'senha': senha,
            'titulo': f'{voluntario.nomecompleto_voluntario} entrou na equipe',
        })
    return render(request, 'painel/adicionar.html', {'form': form, 'para_mim': para_mim})


@painel_required
def pessoa_adicionar(request):
    return _adicionar(request, para_mim=False)


@painel_required
def eu_atendo(request):
    if voluntario_de(request.user) is not None:
        messages.info(request, 'Você já faz parte da equipe de atendimento.')
        return redirect('painel_equipe')
    return _adicionar(request, para_mim=True)


def _pessoa(request, id_voluntario):
    pessoa = get_object_or_404(
        Voluntario.objects.select_related('usuario', 'estagiario', 'advogado', 'bacharel'), pk=id_voluntario)
    if pessoa.usuario_id and pessoa.usuario.is_superuser and not request.user.is_superuser:
        raise Http404
    return pessoa


@painel_required
def pessoa(request, id_voluntario):
    alvo = _pessoa(request, id_voluntario)
    form = EditarPessoaForm(request.POST or None, instance=alvo)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Dados atualizados.')
        return redirect('painel_pessoa', alvo.pk)
    return render(request, 'painel/pessoa.html', {
        'pessoa': alvo,
        'form': form,
        'vinculos': alvo.vinculos.filter(fim__isnull=True).select_related('assistida'),
        'na_coordenacao': bool(alvo.usuario_id) and e_coordenacao(alvo.usuario),
        'sou_eu': alvo.usuario_id == request.user.pk,
    })


@painel_required
@require_POST
def pessoa_acesso(request, id_voluntario, acao):
    alvo = _pessoa(request, id_voluntario)
    usuario = alvo.usuario
    voltar = redirect('painel_pessoa', alvo.pk)

    if acao == 'criar':
        if usuario is None:
            with transaction.atomic():
                usuario, senha = criar_acesso(alvo)
                registrar(request, 'usuario_vinculado')
            return _mostrar_senha(request, alvo, usuario, senha, f'Acesso criado para {alvo.nomecompleto_voluntario}')
        return voltar
    if usuario is None:
        raise Http404
    if acao == 'redefinir':
        senha = senha_temporaria()
        with transaction.atomic():
            usuario.set_password(senha)
            usuario.save()
            ContaInterna.objects.update_or_create(usuario=usuario, defaults={'trocar_senha': True})
            registrar(request, 'senha_redefinida')
        return _mostrar_senha(request, alvo, usuario, senha, f'Nova senha de {alvo.nomecompleto_voluntario}')
    if usuario == request.user:
        messages.error(request, 'Você não pode alterar o próprio acesso. Peça a outra pessoa da coordenação.')
        return voltar
    if acao in ('desativar', 'reativar'):
        with transaction.atomic():
            usuario.is_active = acao == 'reativar'
            usuario.save(update_fields=['is_active'])
            registrar(request, 'acesso_alterado')
        messages.success(request, 'Acesso atualizado.')
        return voltar
    if acao in ('dar_coordenacao', 'tirar_coordenacao'):
        with transaction.atomic():
            definir_coordenacao(usuario, acao == 'dar_coordenacao')
            registrar(request, 'acesso_alterado')
        messages.success(request, 'Acesso atualizado.')
        return voltar
    raise Http404


def _mostrar_senha(request, voluntario, usuario, senha, titulo):
    return render(request, 'painel/acesso_criado.html', {
        'voluntario': voluntario, 'usuario': usuario, 'senha': senha, 'titulo': titulo,
    })


# ------------------------------------------------------------------ demais telas
@painel_required
def pendencias(request):
    consulta = PendenciaCadastro.objects.filter(resolvida_em__isnull=True)
    return render(request, 'painel/pendencias.html', {'pagina': _pagina(request, consulta)})


@painel_required
@require_POST
def pendencia_resolver(request, id_pendencia):
    pendencia = get_object_or_404(PendenciaCadastro, pk=id_pendencia, resolvida_em__isnull=True)
    pendencia.resolvida_em = timezone.now()
    pendencia.save()
    messages.success(request, 'Pendência resolvida.')
    return redirect('painel_pendencias')


@painel_required
def atendimentos(request):
    form = AtendimentoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Atendimento agendado.')
        return redirect('painel_atendimentos')
    consulta = Atendimento.objects.select_related('id_assistida', 'id_estagiario__id_voluntario').order_by(
        '-data_atendimento', '-hora_atendimento')
    return render(request, 'painel/atendimentos.html', {'form': form, 'pagina': _pagina(request, consulta)})


@painel_required
@require_POST
def atendimento_cancelar(request, id_atendimento):
    get_object_or_404(Atendimento, pk=id_atendimento).delete()
    messages.success(request, 'Atendimento cancelado.')
    return redirect('painel_atendimentos')


@painel_required
def acessos(request):
    login = request.GET.get('login', '').strip()
    acao = request.GET.get('acao', '')
    consulta = RegistroAcesso.objects.all()
    if login:
        consulta = consulta.filter(login__icontains=login)
    if acao:
        consulta = consulta.filter(acao=acao)
    return render(request, 'painel/acessos.html', {
        'pagina': _pagina(request, consulta, 50), 'login': login, 'acao': acao, 'acoes': RegistroAcesso.ACOES,
    })
