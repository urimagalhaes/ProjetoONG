from datetime import date, time

from django.db import IntegrityError, transaction
from django.test import TestCase

from assistidas.tests import criar_advogada, criar_assistida
from atendimentos.models import Atendimento
from voluntarios.models import Advogado, Estagiario, Voluntario


class AtendimentoTests(TestCase):
    def test_cria_atendimento_sem_estagiario(self):
        a = criar_assistida()
        at = Atendimento.objects.create(id_assistida=a, data_atendimento=date(2026, 11, 3), hora_atendimento=time(15, 0))
        self.assertIn('Maria da Silva', str(at))

    def criar_estagiario(self, cpf):
        v = criar_advogada()
        Voluntario.objects.filter(pk=v.pk).update(cpf_hash_voluntario=cpf)
        Advogado.objects.filter(id_voluntario=v).delete()
        return Estagiario.objects.create(id_voluntario=v, curso_estagiario='Direito', periodo_estagiario='7')

    def test_estagiario_nao_atende_duas_no_mesmo_horario(self):
        a = criar_assistida()
        b = criar_assistida(cpf_assistida='222.222.222-22', nome_assistida='Outra')
        est = self.criar_estagiario('um')
        horario = dict(data_atendimento=date(2026, 11, 3), hora_atendimento=time(15, 0))
        Atendimento.objects.create(id_assistida=a, id_estagiario=est, **horario)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Atendimento.objects.create(id_assistida=b, id_estagiario=est, **horario)

    def test_dois_estagiarios_podem_atender_no_mesmo_horario(self):
        a = criar_assistida()
        b = criar_assistida(cpf_assistida='222.222.222-22', nome_assistida='Outra')
        horario = dict(data_atendimento=date(2026, 11, 3), hora_atendimento=time(15, 0))
        Atendimento.objects.create(id_assistida=a, id_estagiario=self.criar_estagiario('um'), **horario)
        Atendimento.objects.create(id_assistida=b, id_estagiario=self.criar_estagiario('dois'), **horario)
        self.assertEqual(Atendimento.objects.count(), 2)

    def test_rota_de_teste_foi_removida(self):
        self.assertEqual(self.client.get('/api/atendimentos/adicionar/').status_code, 404)
