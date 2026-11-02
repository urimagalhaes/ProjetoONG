"""
Ponto único das regras de acesso a assistidas e prontuários.

Só o vínculo ativo dá acesso ao prontuário, inclusive para a Coordenação e para
superusuários. Por isso estas regras não usam has_perm nem is_superuser.
"""
from .models import Assistida, VinculoAtendimento

GRUPO_COORDENACAO = 'Coordenação'
GRUPO_ATENDIMENTO = 'Atendimento'


def voluntario_de(usuario):
    if not usuario.is_authenticated:
        return None
    return getattr(usuario, 'voluntario', None)


def e_coordenacao(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name=GRUPO_COORDENACAO).exists()


def pode_usar_painel(usuario):
    """Só abre a gestão. Não dá acesso a prontuário."""
    return usuario.is_authenticated and (usuario.is_superuser or e_coordenacao(usuario))


def tem_vinculo_ativo(usuario, id_assistida):
    voluntario = voluntario_de(usuario)
    if voluntario is None:
        return False
    return VinculoAtendimento.objects.filter(
        assistida_id=id_assistida, voluntario=voluntario, fim__isnull=True).exists()


def assistidas_vinculadas(usuario):
    voluntario = voluntario_de(usuario)
    if voluntario is None:
        return Assistida.objects.none()
    return Assistida.objects.filter(
        vinculos__voluntario=voluntario, vinculos__fim__isnull=True).distinct()


def pode_editar_registro(usuario, registro):
    voluntario = voluntario_de(usuario)
    return (voluntario is not None
            and registro.id_autor_id == voluntario.pk
            and tem_vinculo_ativo(usuario, registro.id_assistida_id))
