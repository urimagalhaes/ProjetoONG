"""
Popula o banco LOCAL com dados fictícios para testar o sistema.

    python manage.py seed_dev

- Só roda com DEBUG=True (nunca em produção).
- Pode ser executado várias vezes: não duplica registros.
- Cria o usuário de teste  admin / admin  caso não exista nenhum superusuário.
- Cria logins de teste, com senha igual ao nome:
  coordenadora, helena (advogada), paula (psicóloga) e carlos (estagiário).
"""
from datetime import date, time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from assistidas.models import Assistida, RegistroProntuario, VinculoAtendimento
from assistidas.permissoes import GRUPO_ATENDIMENTO, GRUPO_COORDENACAO
from atendimentos.models import Atendimento
from core.models import ContaInterna
from voluntarios.models import (
    Advogado, Bacharel, DisponibilidadeEstagiario, Estagiario, Voluntario,
)


class Command(BaseCommand):
    help = 'Cria dados fictícios (assistidas, voluntários, prontuários) para testes locais.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_dev só pode ser usado com DEBUG=True.')

        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            self.stdout.write('Superusuário de teste criado: admin / admin')

        def voluntario(cpf, nome, **extra):
            base = dict(
                email_voluntario=f'{nome.split()[0].lower()}@example.com',
                nomecompleto_voluntario=nome,
                datanasc_voluntario=date(1995, 5, 20),
                sexo_voluntario='F',
                cidade_voluntario='Niterói', estado_voluntario='RJ',
                endereco_voluntario='Rua Fictícia, 100',
                telefone_voluntario='999990000',
                instagram_voluntario='@exemplo',
                rg_voluntario='123456789',
                cpfupload_voluntario=True, fotoupload_voluntario=True,
                termoupload_voluntario=True,
            )
            base.update(extra)
            obj, _ = Voluntario.objects.get_or_create(cpf_voluntario=cpf, defaults=base)
            return obj

        v_adv = voluntario('000.000.000-01', 'Helena Advogada (teste)')
        Advogado.objects.get_or_create(id_voluntario=v_adv, defaults={'oab_advogado': 'RJ000001'})

        v_bac = voluntario('000.000.000-02', 'Paula Psicóloga (teste)')
        Bacharel.objects.get_or_create(id_voluntario=v_bac, defaults={'cursoformacao_bacharel': 'Psicologia'})

        v_est = voluntario('000.000.000-03', 'Carlos Estagiário (teste)', sexo_voluntario='M')
        est, _ = Estagiario.objects.get_or_create(
            id_voluntario=v_est, defaults={'curso_estagiario': 'Direito', 'periodo_estagiario': '7'})
        if not est.disponibilidades.exists():
            for dia in ('TER', 'QUI'):
                DisponibilidadeEstagiario.objects.create(
                    id_estagiario=est, diasemana_estagiario=dia,
                    iniciodisponibilidade_estagiario=time(14, 0),
                    fimdisponibilidade_estagiario=time(18, 0))

        def assistida(cpf, nome, apelido, idade):
            obj, _ = Assistida.objects.get_or_create(cpf_assistida=cpf, defaults=dict(
                nome_assistida=nome, apelido_assistida=apelido, idade_assistida=idade,
                cep_assistida='24020000', rua_assistida='Rua Exemplo', num_endereco_assistida='42',
                telefone_assistida='21999990000', melhor_horario='de manhã',
                cidade_assistida='Niterói', estado_assistida='RJ'))
            return obj

        a1 = assistida('111.111.111-11', 'Maria da Silva (teste)', 'Mari', 34)
        a2 = assistida('222.222.222-22', 'Joana Souza (teste)', None, 27)
        assistida('333.333.333-33', 'Ana Lima (teste)', 'Aninha', 41)

        if not a1.registros_prontuario.exists():
            RegistroProntuario.objects.create(
                id_assistida=a1, id_autor=v_adv,
                texto='Primeiro atendimento jurídico.\nRelatou histórico de ameaças; orientada sobre medida protetiva.')
            RegistroProntuario.objects.create(
                id_assistida=a1, id_autor=v_bac,
                texto='Acolhimento psicológico inicial. Retorno agendado para a próxima semana.')
        if not a2.registros_prontuario.exists():
            RegistroProntuario.objects.create(
                id_assistida=a2, id_autor=v_est, texto='Triagem realizada. Encaminhada para advogada voluntária.')

        def login(nome, voluntario=None, grupo=GRUPO_ATENDIMENTO, staff=False):
            usuario, criado = User.objects.get_or_create(username=nome, defaults={'is_staff': staff})
            if criado:
                usuario.set_password(nome)
                usuario.save()
            usuario.groups.add(Group.objects.get(name=grupo))
            if voluntario is not None:
                voluntario.usuario = usuario
                voluntario.save()
            return usuario

        coordenadora = login('coordenadora', grupo=GRUPO_COORDENACAO, staff=True)
        login('helena', v_adv)
        login('paula', v_bac)
        login('carlos', v_est)
        for usuario in User.objects.all():
            ContaInterna.objects.update_or_create(usuario=usuario, defaults={'trocar_senha': False})

        for alvo, quem in ((a1, v_adv), (a1, v_bac), (a2, v_est)):
            VinculoAtendimento.objects.get_or_create(
                assistida=alvo, voluntario=quem, fim=None, defaults={'designado_por': coordenadora})

        Atendimento.objects.get_or_create(
            data_atendimento=date(2026, 11, 3), hora_atendimento=time(15, 0),
            defaults={'id_assistida': a1, 'id_estagiario': est})

        self.stdout.write(self.style.SUCCESS(
            f'OK — {Assistida.objects.count()} assistidas, {Voluntario.objects.count()} voluntários, '
            f'{RegistroProntuario.objects.count()} registros de prontuário.'))
