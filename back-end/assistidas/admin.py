from functools import wraps

from django.contrib import admin, messages
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.cache import add_never_cache_headers

from . import direitos
from .auditoria import registrar
from .forms import AssistidaAdminForm, VinculoAdminForm
from .models import Assistida, PendenciaCadastro, RegistroAcesso, VinculoAtendimento

# RegistroProntuario não entra no admin de propósito: o texto só abre pelas telas
# de /assistidas/, onde a regra de vínculo vale inclusive para superusuários.


def acao_confirmada(descricao, aviso, botao):
    """Ação do admin para uma assistida por vez, sempre com tela de confirmação."""
    def decorar(funcao):
        @admin.action(description=descricao, permissions=['change'])
        @wraps(funcao)
        def acao(self, request, queryset):
            if queryset.count() != 1:
                self.message_user(request, 'Selecione uma assistida por vez.', messages.ERROR)
                return None
            assistida = queryset.get()
            if 'confirmado' not in request.POST:
                return render(request, 'admin/assistidas/assistida/confirmar_acao.html', {
                    **self.admin_site.each_context(request),
                    'title': descricao,
                    'assistida': assistida,
                    'acao': funcao.__name__,
                    'aviso': aviso,
                    'botao': botao,
                })
            return funcao(self, request, assistida)
        return acao
    return decorar


@admin.register(Assistida)
class AssistidaAdmin(admin.ModelAdmin):
    form = AssistidaAdminForm
    list_display = [
        'id_assistida',
        'nome_assistida',
        'idade_assistida',
        'cidade_assistida',
        'estado_assistida',
    ]
    list_filter = ['estado_assistida', 'cidade_assistida']
    search_fields = ['nome_assistida', 'apelido_assistida']
    readonly_fields = ['id_assistida']
    list_per_page = 25
    actions = ['exportar_dados', 'anonimizar', 'excluir_definitivamente']

    fieldsets = (
        ('Informações Pessoais', {
            'fields': (
                'id_assistida',
                'nome_assistida',
                'cpf_assistida',
                'idade_assistida',
                'apelido_assistida',
            )
        }),
        ('Contato', {
            'fields': (
                'telefone_assistida',
                'pode_deixar_recado',
                'melhor_horario',
            )
        }),
        ('Endereço', {
            'fields': (
                'cep_assistida',
                'rua_assistida',
                'num_endereco_assistida',
                'complemento_endereco_assistida',
                'cidade_assistida',
                'estado_assistida',
            )
        }),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.anonimizada:
            return False
        return super().has_change_permission(request, obj)

    @acao_confirmada(
        'Exportar dados da titular (JSON)',
        'Gera um arquivo com os dados da titular. O prontuário só entra se você tiver vínculo ativo com ela. '
        'A exportação fica registrada.',
        'Exportar',
    )
    def exportar_dados(self, request, assistida):
        resposta = JsonResponse(
            direitos.dados_para_exportar(request, assistida),
            json_dumps_params={'ensure_ascii': False, 'indent': 2})
        resposta['Content-Disposition'] = f'attachment; filename="assistida-{assistida.pk}.json"'
        add_never_cache_headers(resposta)
        return resposta

    @acao_confirmada(
        'Anonimizar assistida',
        'Apaga dados pessoais, prontuário e cópias do cadastro, e encerra os vínculos. Ficam só idade e UF. '
        'Não pode ser desfeito.',
        'Anonimizar',
    )
    def anonimizar(self, request, assistida):
        direitos.anonimizar(request, assistida)
        self.message_user(request, 'Assistida anonimizada.', messages.SUCCESS)

    @acao_confirmada(
        'Excluir definitivamente',
        'Apaga o cadastro, o prontuário, os vínculos, os atendimentos e as cópias do cadastro. '
        'Não pode ser desfeito.',
        'Excluir definitivamente',
    )
    def excluir_definitivamente(self, request, assistida):
        direitos.excluir(request, assistida)
        self.message_user(request, 'Assistida excluída.', messages.SUCCESS)


@admin.register(PendenciaCadastro)
class PendenciaCadastroAdmin(admin.ModelAdmin):
    list_display = ['id_pendencia', 'tipo', 'criado_em', 'resolvida_em']
    list_filter = ['tipo', 'resolvida_em']
    readonly_fields = ['id_pendencia', 'tipo', 'dados', 'criado_em', 'resolvida_em']
    actions = ['marcar_resolvida']

    def has_add_permission(self, request):
        return False

    @admin.action(description='Marcar como resolvida')
    def marcar_resolvida(self, request, queryset):
        queryset.filter(resolvida_em__isnull=True).update(resolvida_em=timezone.now())


@admin.register(VinculoAtendimento)
class VinculoAtendimentoAdmin(admin.ModelAdmin):
    form = VinculoAdminForm
    list_display = ['assistida', 'voluntario', 'designado_por', 'inicio', 'fim']
    list_filter = [('fim', admin.EmptyFieldListFilter)]
    search_fields = ['assistida__nome_assistida', 'voluntario__nomecompleto_voluntario']
    fields = ['assistida', 'voluntario', 'designado_por', 'inicio', 'fim']
    actions = ['encerrar']

    def get_readonly_fields(self, request, obj=None):
        fixos = ['designado_por', 'inicio', 'fim']
        return fixos + ['assistida', 'voluntario'] if obj else fixos

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            return
        obj.designado_por = request.user
        obj.save()
        registrar(request, 'vinculo_criado', id_assistida=obj.assistida_id)

    @admin.action(description='Encerrar vínculo', permissions=['change'])
    def encerrar(self, request, queryset):
        for vinculo in queryset.filter(fim__isnull=True):
            vinculo.fim = timezone.now()
            vinculo.save()
            registrar(request, 'vinculo_encerrado', id_assistida=vinculo.assistida_id)


@admin.register(RegistroAcesso)
class RegistroAcessoAdmin(admin.ModelAdmin):
    list_display = ['criado_em', 'login', 'acao', 'id_assistida', 'id_registro', 'ip']
    list_filter = ['acao', 'criado_em']
    search_fields = ['login', 'id_assistida']
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
