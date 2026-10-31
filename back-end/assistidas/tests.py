import json
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.cadastro import VERSAO_AVISO
from core.models import ContaInterna
from core.utils_teste import STORAGES_TESTE
from voluntarios.models import Advogado, Voluntario
from .models import Assistida, PendenciaCadastro, RegistroProntuario, VinculoAtendimento
from .permissoes import GRUPO_ATENDIMENTO, GRUPO_COORDENACAO

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
        a = Assistida.objects.get()
        self.assertEqual(a.cpf_assistida, '529.982.247-25')
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


@override_settings(STORAGES=STORAGES_TESTE)
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


def criar_login(nome, voluntario=None, **kw):
    usuario = get_user_model().objects.create_user(nome, password='x', **kw)
    ContaInterna.objects.create(usuario=usuario, trocar_senha=False)
    if voluntario is not None:
        voluntario.usuario = usuario
        voluntario.save()
    return usuario


@override_settings(STORAGES=STORAGES_TESTE)
class AreaInternaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maria = criar_assistida()
        cls.joana = criar_assistida(cpf_assistida='222.222.222-22', nome_assistida='Joana Souza')
        cls.autora = criar_advogada()
        cls.atendente = criar_login('atendente', cls.autora)
        cls.vinculo = VinculoAtendimento.objects.create(assistida=cls.maria, voluntario=cls.autora)

    def url(self, assistida):
        return reverse('assistida_prontuario', args=[assistida.pk])

    def test_anonimo_vai_para_login(self):
        for url in (reverse('assistidas_lista'), self.url(self.maria)):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn('/entrar/', r['Location'])

    def test_lista_mostra_so_as_vinculadas(self):
        self.client.force_login(self.atendente)
        r = self.client.get(reverse('assistidas_lista'))
        self.assertContains(r, 'Maria da Silva')
        self.assertNotContains(r, 'Joana Souza')

    def test_busca_fica_dentro_das_vinculadas(self):
        self.client.force_login(self.atendente)
        r = self.client.get(reverse('assistidas_lista'), {'q': 'joana'})
        self.assertNotContains(r, 'Joana Souza')

    def test_busca_por_cpf_e_exata(self):
        self.client.force_login(self.atendente)
        r = self.client.get(reverse('assistidas_lista'), {'q': '111.111.111-11'})
        self.assertContains(r, 'Maria da Silva')
        r = self.client.get(reverse('assistidas_lista'), {'q': '111.111'})
        self.assertNotContains(r, 'Maria da Silva')

    def test_prontuario_mostra_autor_tipo_e_texto(self):
        RegistroProntuario.objects.create(id_assistida=self.maria, id_autor=self.autora, texto='Linha 1\nLinha 2')
        self.client.force_login(self.atendente)
        r = self.client.get(self.url(self.maria))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Prontuário de Maria da Silva')
        self.assertContains(r, 'Helena Advogada')
        self.assertContains(r, 'Advogado(a)')
        self.assertContains(r, 'Linha 1<br>Linha 2')

    def test_prontuario_mostra_contato_e_alerta_de_recado(self):
        Assistida.objects.filter(pk=self.maria.pk).update(
            telefone_assistida='21999990000', melhor_horario='de manhã')
        self.client.force_login(self.atendente)
        r = self.client.get(self.url(self.maria))
        self.assertContains(r, '21999990000')
        self.assertContains(r, 'de manhã')
        self.assertContains(r, 'Não deixar recado')

    def test_prontuario_escapa_html(self):
        RegistroProntuario.objects.create(
            id_assistida=self.maria, id_autor=self.autora, texto='<script>alert(1)</script>')
        self.client.force_login(self.atendente)
        r = self.client.get(self.url(self.maria))
        self.assertNotContains(r, '<script>alert(1)</script>')
        self.assertContains(r, '&lt;script&gt;')

    def test_paginas_nao_ficam_em_cache(self):
        self.client.force_login(self.atendente)
        self.assertIn('no-store', self.client.get(self.url(self.maria))['Cache-Control'])

    def test_voluntario_com_registro_nao_pode_ser_apagado(self):
        from django.db.models import ProtectedError
        RegistroProntuario.objects.create(id_assistida=self.maria, id_autor=self.autora, texto='x')
        with self.assertRaises(ProtectedError):
            self.autora.delete()


@override_settings(STORAGES=STORAGES_TESTE)
class AdminTests(TestCase):
    def test_telas_abrem(self):
        root = get_user_model().objects.create_superuser('root', 'r@example.com', 'x')
        ContaInterna.objects.create(usuario=root, trocar_senha=False)
        self.client.force_login(root)
        maria = criar_assistida()
        autora = criar_advogada()
        RegistroProntuario.objects.create(id_assistida=maria, id_autor=autora, texto='x')
        PendenciaCadastro.objects.create(tipo='assistida', dados={'nome': 'Teste'})
        for nome in ('assistidas_assistida_changelist', 'assistidas_pendenciacadastro_changelist',
                     'voluntarios_voluntario_changelist', 'atendimentos_atendimento_changelist'):
            self.assertEqual(self.client.get(reverse(f'admin:{nome}')).status_code, 200, nome)
        self.assertEqual(
            self.client.get(reverse('admin:assistidas_assistida_change', args=[maria.pk])).status_code, 200)


@override_settings(STORAGES=STORAGES_TESTE)
class MatrizDeAcessoAoProntuarioTests(TestCase):
    """Só o vínculo ativo abre o prontuário; sem ele a resposta é sempre 404."""

    @classmethod
    def setUpTestData(cls):
        cls.maria = criar_assistida()
        cls.autora = criar_advogada()
        cls.url = reverse('assistida_prontuario', args=[cls.maria.pk])
        cls.inexistente = reverse('assistida_prontuario', args=[9999])
        RegistroProntuario.objects.create(id_assistida=cls.maria, id_autor=cls.autora, texto='SIGILOSO')

    def status(self, usuario, url=None):
        self.client.force_login(usuario)
        return self.client.get(url or self.url).status_code

    def test_com_vinculo_ativo_abre(self):
        usuario = criar_login('a', self.autora)
        VinculoAtendimento.objects.create(assistida=self.maria, voluntario=self.autora)
        self.assertEqual(self.status(usuario), 200)

    def test_sem_vinculo_da_404(self):
        self.assertEqual(self.status(criar_login('a', self.autora)), 404)

    def test_login_sem_voluntario_da_404(self):
        self.assertEqual(self.status(criar_login('a')), 404)

    def test_vinculo_encerrado_da_404(self):
        usuario = criar_login('a', self.autora)
        VinculoAtendimento.objects.create(
            assistida=self.maria, voluntario=self.autora, fim=timezone.now())
        self.assertEqual(self.status(usuario), 404)

    def test_coordenacao_sem_vinculo_da_404(self):
        usuario = criar_login('c', is_staff=True)
        usuario.groups.add(Group.objects.get(name=GRUPO_COORDENACAO))
        self.assertEqual(self.status(usuario), 404)

    def test_superusuario_sem_vinculo_da_404(self):
        self.assertEqual(self.status(criar_login('s', is_superuser=True, is_staff=True)), 404)

    def test_coordenacao_com_vinculo_abre(self):
        usuario = criar_login('c', self.autora, is_staff=True)
        usuario.groups.add(Group.objects.get(name=GRUPO_COORDENACAO))
        VinculoAtendimento.objects.create(assistida=self.maria, voluntario=self.autora)
        self.assertEqual(self.status(usuario), 200)

    def test_negado_e_inexistente_respondem_igual(self):
        usuario = criar_login('a', self.autora)
        self.assertEqual(self.status(usuario), self.status(usuario, self.inexistente))


class VinculoTests(TestCase):
    def test_um_vinculo_ativo_por_par_e_historico_preservado(self):
        maria, autora = criar_assistida(), criar_advogada()
        VinculoAtendimento.objects.create(assistida=maria, voluntario=autora, fim=timezone.now())
        VinculoAtendimento.objects.create(assistida=maria, voluntario=autora)
        with self.assertRaises(IntegrityError), transaction.atomic():
            VinculoAtendimento.objects.create(assistida=maria, voluntario=autora)


class GruposTests(TestCase):
    def test_grupos_existem_e_coordenacao_nao_le_prontuario(self):
        self.assertTrue(Group.objects.filter(name=GRUPO_ATENDIMENTO).exists())
        coordenacao = Group.objects.get(name=GRUPO_COORDENACAO)
        codigos = set(coordenacao.permissions.values_list('codename', flat=True))
        self.assertIn('view_assistida', codigos)
        self.assertNotIn('view_registroprontuario', codigos)
        self.assertNotIn('change_registroprontuario', codigos)
