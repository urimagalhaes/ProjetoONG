from django.utils.functional import SimpleLazyObject

from assistidas.permissoes import pode_usar_painel


def acesso(request):
    return {'pode_painel': SimpleLazyObject(lambda: pode_usar_painel(request.user))}
