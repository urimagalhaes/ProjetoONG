from django.conf import settings
from django.shortcuts import redirect

from .models import ContaInterna

# Áreas com dados internos. Uma área nova precisa entrar aqui.
PREFIXOS_INTERNOS = ('/assistidas/', '/painel/', '/admin/')


class ExigenciasDeContaMiddleware:
    """Antes da área interna: senha própria e, depois, segundo fator confirmado."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.path.startswith(PREFIXOS_INTERNOS):
            conta, _ = ContaInterna.objects.get_or_create(usuario=request.user)
            if conta.trocar_senha:
                return redirect('trocar_senha')
            if settings.EXIGIR_2FA and not request.user.is_verified():
                return redirect('verificar_2fa')
        return self.get_response(request)
