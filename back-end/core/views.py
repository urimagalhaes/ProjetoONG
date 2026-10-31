import hmac

from django.conf import settings
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .cadastro import VERSAO_AVISO

def index(request):
    return render(request, 'front/index.html')

def cadastro_assistida(request):
    return render(request, 'front/cadastro-assistida.html')

def privacidade(request):
    return render(request, 'front/privacidade.html', {'versao_aviso': VERSAO_AVISO})

def voluntarios(request):
    return render(request, 'front/voluntarios.html')

def voluntario_advogado(request):
    return render(request, 'front/voluntario-advogado.html')

def voluntario_bacharel(request):
    return render(request, 'front/voluntario-bacharel.html')

def voluntario_estagiario(request):
    return render(request, 'front/voluntario-estagiario.html')

def noticia_campanha(request):
    return render(request, 'front/noticia-campanha-nacional.html')

def noticia_parceria(request):
    return render(request, 'front/noticia-parceria-universidades.html')

def noticia_novo_centro(request):
    return render(request, 'front/noticia-novo-centro-atendimento.html')


@never_cache
@require_GET
def manter_banco(request):
    """Consulta diária do cron, para o Supabase Free não pausar por inatividade."""
    esperado = f'Bearer {settings.CRON_SECRET}'.encode()
    recebido = request.headers.get('Authorization', '').encode()
    if not settings.CRON_SECRET or not hmac.compare_digest(recebido, esperado):
        raise Http404
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return JsonResponse({'ok': True})
