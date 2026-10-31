from django.shortcuts import render

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