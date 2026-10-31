from django.apps import AppConfig
from django.db.models.signals import post_migrate


# As permissões só existem depois do migrate, por isso os grupos são montados
# neste sinal, e não numa data migration.
PERMISSOES_COORDENACAO = {
    'assistidas': {
        'assistida': ('add', 'change', 'view'),
        'vinculoatendimento': ('add', 'change', 'view'),
        'pendenciacadastro': ('change', 'view'),
        'registroacesso': ('view',),
    },
    'voluntarios': {
        'voluntario': ('add', 'change', 'view'),
        'estagiario': ('add', 'change', 'view'),
        'advogado': ('add', 'change', 'view'),
        'bacharel': ('add', 'change', 'view'),
        'disponibilidadeestagiario': ('add', 'change', 'delete', 'view'),
    },
    'atendimentos': {
        'atendimento': ('add', 'change', 'delete', 'view'),
    },
    'auth': {
        'user': ('add', 'change', 'view'),
    },
}


def montar_grupos(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission

    from .permissoes import GRUPO_ATENDIMENTO, GRUPO_COORDENACAO

    Group.objects.get_or_create(name=GRUPO_ATENDIMENTO)
    coordenacao, _ = Group.objects.get_or_create(name=GRUPO_COORDENACAO)
    permissoes = []
    for app, modelos in PERMISSOES_COORDENACAO.items():
        for modelo, acoes in modelos.items():
            permissoes += Permission.objects.filter(
                content_type__app_label=app,
                codename__in=[f'{acao}_{modelo}' for acao in acoes])
    coordenacao.permissions.set(permissoes)


class AssistidasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assistidas'
    verbose_name = 'Assistidas'

    def ready(self):
        post_migrate.connect(montar_grupos, sender=self)
