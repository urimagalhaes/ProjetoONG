from datetime import date, time

from django.db import IntegrityError, transaction
from django.test import TestCase

from assistidas.tests import criar_assistida
from atendimentos.models import Atendimento


class AtendimentoTests(TestCase):
    def test_cria_atendimento_sem_estagiario(self):
        a = criar_assistida()
        at = Atendimento.objects.create(id_assistida=a, data_atendimento=date(2026, 11, 3), hora_atendimento=time(15, 0))
        self.assertIn('Maria da Silva', str(at))

    def test_mesmo_horario_nao_duplica(self):
        a = criar_assistida()
        b = criar_assistida(cpf_assistida='222.222.222-22', nome_assistida='Outra')
        Atendimento.objects.create(id_assistida=a, data_atendimento=date(2026, 11, 3), hora_atendimento=time(15, 0))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Atendimento.objects.create(id_assistida=b, data_atendimento=date(2026, 11, 3), hora_atendimento=time(15, 0))

    def test_rota_de_teste_foi_removida(self):
        self.assertEqual(self.client.get('/api/atendimentos/adicionar/').status_code, 404)
