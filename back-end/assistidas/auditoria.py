from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address

from .models import RegistroAcesso


def _ip(request):
    encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
    ip = encaminhado or request.META.get('REMOTE_ADDR')
    try:
        validate_ipv46_address(ip)
    except ValidationError:
        return None
    return ip


def registrar(request, acao, id_assistida=None, id_registro=None):
    usuario = request.user if request.user.is_authenticated else None
    RegistroAcesso.objects.create(
        usuario=usuario,
        login=usuario.get_username() if usuario else '',
        acao=acao,
        id_assistida=id_assistida,
        id_registro=id_registro,
        ip=_ip(request),
    )
