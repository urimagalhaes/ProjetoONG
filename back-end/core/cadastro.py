"""
Recebimento dos cadastros públicos (assistidas e voluntários).

A resposta é a mesma com CPF novo ou repetido: quem usa o formulário não pode
descobrir se alguém já está cadastrado. Um envio repetido nunca altera o
cadastro existente; ele vira uma PendenciaCadastro para a coordenação.
"""
import json
import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone

from assistidas.models import PendenciaCadastro

logger = logging.getLogger(__name__)

# Trocar a cada mudança no texto de core/templates/front/privacidade.html.
VERSAO_AVISO = '2026-10-31'


def _resposta_recebido():
    return JsonResponse({
        'success': True,
        'message': 'Cadastro recebido! Entraremos em contato em breve.',
    }, status=201)


def _resposta_erro(mensagem, status=400, **extras):
    return JsonResponse({'success': False, 'message': mensagem, **extras}, status=status)


def texto(data, campo):
    valor = data.get(campo)
    return '' if valor is None else str(valor).strip()


def dados_do_aceite():
    return {'aceite_aviso_em': timezone.now(), 'aceite_aviso_versao': VERSAO_AVISO}


def receber_cadastro(request, tipo, salvar, campos):
    """
    Trata um POST público. `salvar(data)` grava o cadastro e levanta
    ValidationError, com dicionário por campo, se os dados forem inválidos.
    `campos` é a lista do que pode ser copiado para a pendência.
    """
    if request.method != 'POST':
        return _resposta_erro('Método não permitido', status=405)

    try:
        data = json.loads(request.body)
    except ValueError:
        return _resposta_erro('Dados inválidos.')
    if not isinstance(data, dict):
        return _resposta_erro('Dados inválidos.')

    # Campo invisível: só robôs preenchem. Finge sucesso para não ensinar o robô.
    if data.get('website'):
        return _resposta_recebido()

    if data.get('aceite') is not True:
        return _resposta_erro('É preciso aceitar o aviso de privacidade.')

    try:
        try:
            with transaction.atomic():
                salvar(data)
        except IntegrityError:
            PendenciaCadastro.objects.create(
                tipo=tipo,
                dados={
                    **{campo: data.get(campo) for campo in campos},
                    'aceite_aviso_versao': VERSAO_AVISO,
                },
            )
    except ValidationError as erro:
        return _resposta_erro('Confira os dados informados.', campos=sorted(erro.message_dict))
    except Exception as erro:
        # Só o tipo do erro: a mensagem pode trazer dados pessoais.
        logger.error('Falha ao gravar cadastro %s: %s', tipo, type(erro).__name__)
        return _resposta_erro('Não foi possível enviar agora. Tente novamente.', status=500)

    return _resposta_recebido()
