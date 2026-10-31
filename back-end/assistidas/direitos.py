"""
Direitos da titular (LGPD, art. 18): exportar, anonimizar e excluir.

O texto do prontuário só sai na exportação quando quem exporta tem vínculo ativo.
Anonimizar e excluir apagam também as cópias do cadastro: pendências com o mesmo
CPF e o histórico do admin, que guarda o nome da assistida.
"""
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.cripto import hash_cpf
from .auditoria import registrar
from .models import PREFIXO_ANONIMIZADA, PendenciaCadastro
from .permissoes import tem_vinculo_ativo


def dados_para_exportar(request, assistida):
    incluir_prontuario = tem_vinculo_ativo(request.user, assistida.pk)
    dados = {
        'cadastro': {
            'nome': assistida.nome_assistida,
            'apelido': assistida.apelido_assistida,
            'cpf': assistida.cpf_assistida,
            'idade': assistida.idade_assistida,
            'telefone': assistida.telefone_assistida,
            'pode_deixar_recado': assistida.pode_deixar_recado,
            'melhor_horario': assistida.melhor_horario,
            'cep': assistida.cep_assistida,
            'rua': assistida.rua_assistida,
            'numero': assistida.num_endereco_assistida,
            'complemento': assistida.complemento_endereco_assistida,
            'cidade': assistida.cidade_assistida,
            'estado': assistida.estado_assistida,
            'aceite_aviso_em': assistida.aceite_aviso_em,
            'aceite_aviso_versao': assistida.aceite_aviso_versao,
        },
        'atendimentos': [
            {'data': a.data_atendimento, 'hora': a.hora_atendimento}
            for a in assistida.atendimentos.all()
        ],
        'vinculos': [
            {'voluntario': v.voluntario.nomecompleto_voluntario, 'inicio': v.inicio, 'fim': v.fim}
            for v in assistida.vinculos.select_related('voluntario')
        ],
        'prontuario_incluido': incluir_prontuario,
    }
    if incluir_prontuario:
        dados['prontuario'] = [
            {
                'autor': r.id_autor.nomecompleto_voluntario,
                'criado_em': r.criado_em,
                'texto': r.texto,
                'versoes_anteriores': [
                    {'editado_em': v.editado_em, 'texto': v.texto_anterior} for v in r.versoes.all()
                ],
            }
            for r in assistida.registros_prontuario.select_related('id_autor')
        ]
    registrar(request, 'exportacao', id_assistida=assistida.pk)
    return dados


def _apagar_copias(assistida):
    if assistida.cpf_assistida:
        cpf = hash_cpf(assistida.cpf_assistida)
        for pendencia in PendenciaCadastro.objects.filter(tipo='assistida'):
            if hash_cpf(pendencia.dados.get('cpf', '')) == cpf:
                pendencia.delete()
    LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(assistida), object_id=str(assistida.pk)).delete()


@transaction.atomic
def anonimizar(request, assistida):
    """Mantém só idade e UF, para estatística, e encerra os vínculos."""
    _apagar_copias(assistida)
    assistida.registros_prontuario.all().delete()
    assistida.vinculos.filter(fim__isnull=True).update(fim=timezone.now())
    assistida.nome_assistida = f'Anônima #{assistida.pk}'
    assistida.apelido_assistida = None
    assistida.cpf_assistida = ''
    assistida.cpf_hash = f'{PREFIXO_ANONIMIZADA}{assistida.pk}'
    assistida.cep_assistida = ''
    assistida.rua_assistida = ''
    assistida.num_endereco_assistida = ''
    assistida.complemento_endereco_assistida = None
    assistida.cidade_assistida = ''
    assistida.telefone_assistida = ''
    assistida.melhor_horario = ''
    assistida.save()
    registrar(request, 'anonimizacao', id_assistida=assistida.pk)


@transaction.atomic
def excluir(request, assistida):
    id_assistida = assistida.pk
    _apagar_copias(assistida)
    assistida.delete()
    registrar(request, 'exclusao', id_assistida=id_assistida)
