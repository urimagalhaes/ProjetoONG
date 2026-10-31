import json

from django.test import Client, TestCase

from assistidas.models import PendenciaCadastro
from core.cadastro import VERSAO_AVISO
from voluntarios.models import Advogado, Bacharel, Estagiario, Voluntario

BASE = {
    'email': 'c@example.com', 'nome': 'Carlos Teste', 'dataNascimento': '2000-03-10', 'sexo': 'M',
    'cidade': 'Niterói', 'estado': 'RJ', 'endereco': 'Rua C, 5', 'telefone': '999990000',
    'instagram': '', 'cpf': '98765432100', 'rg': '123456789', 'aceite': True,
}
ESTAGIARIO = {**BASE, 'curso': 'Direito', 'periodo': '5'}
ROTA_ESTAGIARIO = '/api/voluntarios/adicionar/estagiario/'
ROTA_ADVOGADO = '/api/voluntarios/adicionar/advogado/'
ROTA_BACHAREL = '/api/voluntarios/adicionar/bacharel/'


class ApiVoluntariosTests(TestCase):
    def post(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def test_cadastra_estagiario(self):
        r = self.post(ROTA_ESTAGIARIO, ESTAGIARIO)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotIn('id', r.json())
        v = Voluntario.objects.get()
        self.assertEqual(v.cpf_voluntario, '987.654.321-00')
        self.assertEqual(Estagiario.objects.get(id_voluntario=v).periodo_estagiario, '5')
        self.assertEqual(v.tipo, 'Estagiário(a)')
        self.assertEqual(v.aceite_aviso_versao, VERSAO_AVISO)

    def test_cadastra_advogado(self):
        r = self.post(ROTA_ADVOGADO, {**BASE, 'oab': 'RJ/123456'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Advogado.objects.get().oab_advogado, 'RJ/123456')

    def test_cadastra_bacharel(self):
        r = self.post(ROTA_BACHAREL, {**BASE, 'cursoBacharel': 'Direito'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Bacharel.objects.get().cursoformacao_bacharel, 'Direito')

    def test_documentos_comecam_como_nao_entregues(self):
        self.post(ROTA_ESTAGIARIO, {**ESTAGIARIO, 'cpfupload': True, 'fotoupload': True, 'termoupload': True})
        v = Voluntario.objects.get()
        self.assertFalse(v.cpfupload_voluntario)
        self.assertFalse(v.fotoupload_voluntario)
        self.assertFalse(v.termoupload_voluntario)

    def test_cpf_repetido_tem_resposta_identica_e_vira_pendencia(self):
        primeira = self.post(ROTA_ESTAGIARIO, ESTAGIARIO)
        segunda = self.post(ROTA_ESTAGIARIO, {**ESTAGIARIO, 'nome': 'Outro Nome'})
        self.assertEqual(segunda.status_code, primeira.status_code)
        self.assertEqual(segunda.content, primeira.content)
        self.assertEqual(Voluntario.objects.get().nomecompleto_voluntario, 'Carlos Teste')
        pendencia = PendenciaCadastro.objects.get()
        self.assertEqual(pendencia.tipo, 'estagiario')
        self.assertEqual(pendencia.dados['nome'], 'Outro Nome')

    def test_oab_repetida_nao_deixa_voluntario_solto(self):
        self.post(ROTA_ADVOGADO, {**BASE, 'oab': 'RJ/123456'})
        r = self.post(ROTA_ADVOGADO, {**BASE, 'cpf': '52998224725', 'oab': 'RJ/123456'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Voluntario.objects.count(), 1)
        self.assertEqual(PendenciaCadastro.objects.get().tipo, 'advogado')

    def test_cpf_invalido_retorna_400(self):
        self.assertEqual(self.post(ROTA_ESTAGIARIO, {**ESTAGIARIO, 'cpf': '11111111111'}).status_code, 400)
        self.assertFalse(Voluntario.objects.exists())

    def test_sem_aceite_e_rejeitado(self):
        self.assertEqual(self.post(ROTA_ESTAGIARIO, {**ESTAGIARIO, 'aceite': False}).status_code, 400)

    def test_dado_de_subtipo_invalido_nao_deixa_voluntario_solto(self):
        r = self.post(ROTA_ESTAGIARIO, {**ESTAGIARIO, 'periodo': '99'})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Voluntario.objects.exists())

    def test_honeypot_finge_sucesso_e_nao_grava(self):
        r = self.post(ROTA_ESTAGIARIO, {**ESTAGIARIO, 'website': 'x'})
        self.assertEqual(r.status_code, 201)
        self.assertFalse(Voluntario.objects.exists())

    def test_csrf_e_exigido(self):
        cliente = Client(enforce_csrf_checks=True)
        for rota in (ROTA_ESTAGIARIO, ROTA_ADVOGADO, ROTA_BACHAREL):
            r = cliente.post(rota, json.dumps(ESTAGIARIO), content_type='application/json')
            self.assertEqual(r.status_code, 403, rota)

    def test_get_nao_permitido(self):
        self.assertEqual(self.client.get(ROTA_ESTAGIARIO).status_code, 405)
