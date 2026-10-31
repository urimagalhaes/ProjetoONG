import json
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.cadastro import VERSAO_AVISO
from voluntarios.models import Advogado, Voluntario
from .models import Assistida, PendenciaCadastro, RegistroProntuario

PAYLOAD = {
    'cpf': '529.982.247-25', 'nome': 'Maria Teste', 'cep': '24020-000', 'idade': 30,
    'apelido': 'Mari', 'cidade': 'Niterói', 'estado': 'RJ', 'rua': 'Rua A',
    'num_endereco': 's/n', 'complementoEndereco': 'ap 1', 'telefone': '(21) 99999-0000',
    'pode_deixar_recado': False, 'melhor_horario': 'manhã', 'aceite': True,
}


def criar_assistida(**kw):
    dados = dict(
        cpf_assistida='111.111.111-11', nome_assistida='Maria da Silva', cep_assistida='24020000',
        idade_assistida=34, cidade_assistida='Niterói', estado_assistida='RJ',
        rua_assistida='Rua A', num_endereco_assistida=1)
    dados.update(kw)
    return Assistida.objects.create(**dados)


def criar_advogada(nome='Helena Advogada'):
    v = Voluntario.objects.create(
        email_voluntario='h@example.com', nomecompleto_voluntario=nome,
        datanasc_voluntario=date(1990, 1, 1), sexo_voluntario='F', cidade_voluntario='Niterói',
        estado_voluntario='RJ', endereco_voluntario='Rua B', telefone_voluntario='999990000',
        instagram_voluntario='@h', cpf_voluntario='000.000.000-01', rg_voluntario='123456789',
        cpfupload_voluntario=True, fotoupload_voluntario=True, termoupload_voluntario=True)
    Advogado.objects.create(id_voluntario=v, oab_advogado='RJ000001')
    return v


class ApiCadastroAssistidaTests(TestCase):
    url = '/api/assistidas/adicionar/'

    def post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type='application/json')

    def test_cadastra_e_nao_devolve_id(self):
        r = self.post(PAYLOAD)
        self.assertEqual(r.status_code, 201)
        self.assertNotIn('id', r.json())
        a = Assistida.objects.get(cpf_assistida='529.982.247-25')
        self.assertEqual(a.nome_assistida, 'Maria Teste')
        self.assertEqual(a.num_endereco_assistida, 's/n')
        self.assertEqual(a.telefone_assistida, '21999990000')
        self.assertEqual(a.cep_assistida, '24020000')
        self.assertIs(a.pode_deixar_recado, False)
        self.assertEqual(a.melhor_horario, 'manhã')

    def test_guarda_data_e_versao_do_aceite(self):
        self.post(PAYLOAD)
        a = Assistida.objects.get()
        self.assertIsNotNone(a.aceite_aviso_em)
        self.assertEqual(a.aceite_aviso_versao, VERSAO_AVISO)

    def test_sem_aceite_e_rejeitado(self):
        r = self.post({**PAYLOAD, 'aceite': False})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Assistida.objects.exists())

    def test_cpf_repetido_tem_resposta_identica(self):
        primeira = self.post(PAYLOAD)
        segunda = self.post(PAYLOAD)
        self.assertEqual(segunda.status_code, primeira.status_code)
        self.assertEqual(segunda.content, primeira.content)

    def test_cpf_repetido_nao_altera_cadastro_e_vira_pendencia(self):
        self.post(PAYLOAD)
        self.post({**PAYLOAD, 'nome': 'Nome Diferente', 'rua': 'Rua Nova'})
        a = Assistida.objects.get()
        self.assertEqual(a.nome_assistida, 'Maria Teste')
        pendencia = PendenciaCadastro.objects.get()
        self.assertEqual(pendencia.tipo, 'assistida')
        self.assertEqual(pendencia.dados['nome'], 'Nome Diferente')
        self.assertEqual(pendencia.dados['rua'], 'Rua Nova')
        self.assertIsNone(pendencia.resolvida_em)

    def test_pendencia_nao_guarda_campos_fora_da_lista(self):
        self.post(PAYLOAD)
        self.post({**PAYLOAD, 'campo_estranho': 'x' * 100})
        self.assertNotIn('campo_estranho', PendenciaCadastro.objects.get().dados)

    def test_cpf_invalido_retorna_400(self):
        self.assertEqual(self.post({**PAYLOAD, 'cpf': '12345678901'}).status_code, 400)
        self.assertFalse(Assistida.objects.exists())

    def test_telefone_invalido_retorna_400(self):
        self.assertEqual(self.post({**PAYLOAD, 'telefone': '123'}).status_code, 400)

    def test_campo_obrigatorio_faltando_retorna_400(self):
        dados = {**PAYLOAD}
        del dados['nome']
        self.assertEqual(self.post(dados).status_code, 400)

    def test_corpo_que_nao_e_objeto_retorna_400(self):
        self.assertEqual(self.post(['lista']).status_code, 400)

    def test_honeypot_finge_sucesso_e_nao_grava(self):
        r = self.post({**PAYLOAD, 'website': 'http://spam.example'})
        self.assertEqual(r.status_code, 201)
        self.assertFalse(Assistida.objects.exists())
        self.assertFalse(PendenciaCadastro.objects.exists())

    def test_erro_interno_nao_vaza_detalhes(self):
        with mock.patch.object(Assistida, 'save', side_effect=RuntimeError('segredo interno')):
            with self.assertLogs('core.cadastro', level='ERROR') as logs:
                r = self.post(PAYLOAD)
        self.assertEqual(r.status_code, 500)
        self.assertNotIn('segredo', r.content.decode())
        self.assertNotIn('segredo', ''.join(logs.output))

    def test_csrf_e_exigido(self):
        cliente = Client(enforce_csrf_checks=True)
        r = cliente.post(self.url, json.dumps(PAYLOAD), content_type='application/json')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Assistida.objects.exists())

    def test_get_nao_permitido(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_json_invalido(self):
        r = self.client.post(self.url, 'não é json', content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_rota_antiga_nao_existe_mais(self):
        self.assertEqual(self.client.post('/api/vitimas/adicionar/').status_code, 404)


# O storage de produção (Manifest) exige `collectstatic`; nos testes usamos o simples.
@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class PaginasPublicasTests(TestCase):
    def test_pagina_de_cadastro(self):
        r = self.client.get(reverse('cadastro_assistida'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="cpf_assistida"')

    def test_url_antiga_redireciona(self):
        r = self.client.get('/cadastro-vitima/')
        self.assertRedirects(r, '/cadastro-assistida/', status_code=301)

    def test_home_continua_linkando_o_cadastro(self):
        self.assertContains(self.client.get('/'), '/cadastro-assistida/')


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class AreaInternaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.staff = U.objects.create_user('equipe', password='x', is_staff=True)
        cls.comum = U.objects.create_user('comum', password='x')
        cls.maria = criar_assistida()
        cls.joana = criar_assistida(cpf_assistida='222.222.222-22', nome_assistida='Joana Souza')
        cls.autora = criar_advogada()

    def test_anonimo_vai_para_login(self):
        for url in (reverse('assistidas_lista'), reverse('assistida_prontuario', args=[self.maria.pk])):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn('/admin/login/', r['Location'])

    def test_usuario_sem_staff_nao_acessa(self):
        self.client.force_login(self.comum)
        r = self.client.get(reverse('assistidas_lista'))
        self.assertEqual(r.status_code, 302)

    def test_lista_e_busca(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('assistidas_lista'))
        self.assertContains(r, 'Maria da Silva')
        self.assertContains(r, 'Joana Souza')
        r = self.client.get(reverse('assistidas_lista'), {'q': 'joana'})
        self.assertContains(r, 'Joana Souza')
        self.assertNotContains(r, 'Maria da Silva')
        r = self.client.get(reverse('assistidas_lista'), {'q': '111.111'})
        self.assertContains(r, 'Maria da Silva')

    def test_prontuario_mostra_autor_tipo_e_texto(self):
        RegistroProntuario.objects.create(id_assistida=self.maria, id_autor=self.autora, texto='Linha 1\nLinha 2')
        self.client.force_login(self.staff)
        r = self.client.get(reverse('assistida_prontuario', args=[self.maria.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Prontuário de Maria da Silva')
        self.assertContains(r, 'Helena Advogada')
        self.assertContains(r, 'Advogado(a)')
        self.assertContains(r, 'Linha 1<br>Linha 2')

    def test_prontuario_mostra_contato_e_alerta_de_recado(self):
        sem_recado = criar_assistida(
            cpf_assistida='333.333.333-33', telefone_assistida='21999990000', melhor_horario='de manhã')
        self.client.force_login(self.staff)
        r = self.client.get(reverse('assistida_prontuario', args=[sem_recado.pk]))
        self.assertContains(r, '21999990000')
        self.assertContains(r, 'de manhã')
        self.assertContains(r, 'Não deixar recado')

    def test_prontuario_so_mostra_registros_da_propria_assistida(self):
        RegistroProntuario.objects.create(id_assistida=self.joana, id_autor=self.autora, texto='SEGREDO DA JOANA')
        self.client.force_login(self.staff)
        r = self.client.get(reverse('assistida_prontuario', args=[self.maria.pk]))
        self.assertNotContains(r, 'SEGREDO DA JOANA')
        self.assertContains(r, 'Ainda não há registros')

    def test_prontuario_escapa_html(self):
        RegistroProntuario.objects.create(
            id_assistida=self.maria, id_autor=self.autora, texto='<script>alert(1)</script>')
        self.client.force_login(self.staff)
        r = self.client.get(reverse('assistida_prontuario', args=[self.maria.pk]))
        self.assertNotContains(r, '<script>alert(1)</script>')
        self.assertContains(r, '&lt;script&gt;')

    def test_prontuario_inexistente_da_404(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('assistida_prontuario', args=[9999])).status_code, 404)

    def test_paginas_nao_ficam_em_cache(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('assistida_prontuario', args=[self.maria.pk]))
        self.assertIn('no-store', r['Cache-Control'])

    def test_voluntario_com_registro_nao_pode_ser_apagado(self):
        from django.db.models import ProtectedError
        RegistroProntuario.objects.create(id_assistida=self.maria, id_autor=self.autora, texto='x')
        with self.assertRaises(ProtectedError):
            self.autora.delete()

    def test_admin_das_novas_telas_abre(self):
        U = get_user_model()
        U.objects.create_superuser('root', 'r@example.com', 'x')
        self.client.login(username='root', password='x')
        RegistroProntuario.objects.create(id_assistida=self.maria, id_autor=self.autora, texto='x')
        PendenciaCadastro.objects.create(tipo='assistida', dados={'nome': 'Teste'})
        for nome in ('assistidas_assistida_changelist', 'assistidas_registroprontuario_changelist',
                     'assistidas_pendenciacadastro_changelist',
                     'voluntarios_voluntario_changelist', 'atendimentos_atendimento_changelist'):
            self.assertEqual(self.client.get(reverse(f'admin:{nome}')).status_code, 200, nome)
        self.assertEqual(
            self.client.get(reverse('admin:assistidas_assistida_change', args=[self.maria.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:assistidas_registroprontuario_add')).status_code, 200)
