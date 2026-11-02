from datetime import date, time

from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from assistidas.models import (
    Assistida, PendenciaCadastro, RegistroAcesso, RegistroProntuario, VinculoAtendimento,
)
from assistidas.permissoes import GRUPO_ATENDIMENTO, GRUPO_COORDENACAO
from assistidas.tests import criar_advogada, criar_assistida, criar_login
from atendimentos.models import Atendimento
from core.models import ContaInterna
from core.utils_teste import STORAGES_TESTE
from voluntarios.models import Advogado, Bacharel, Voluntario

CPF_A, CPF_B = '529.982.247-25', '987.654.321-00'


def pessoa(**kw):
    return {
        'funcao': 'psicologia', 'nomecompleto_voluntario': 'Lucas Teste', 'email_voluntario': 'lucas@example.com',
        'telefone_voluntario': '(21) 99999-0000', 'datanasc_voluntario': '1990-01-01', 'sexo_voluntario': 'M',
        'cpf_voluntario': CPF_A, 'rg_voluntario': '123456789', 'endereco_voluntario': 'Rua A, 1',
        'cidade_voluntario': 'Niterói', 'estado_voluntario': 'rj', **kw,
    }


@override_settings(STORAGES=STORAGES_TESTE)
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maria = criar_assistida()
        cls.autora = criar_advogada()
        cls.atendente = criar_login('atendente', cls.autora)
        cls.coord = criar_login('coord', is_staff=True)
        cls.coord.groups.add(Group.objects.get(name=GRUPO_COORDENACAO))
        cls.root = criar_login('root', is_staff=True, is_superuser=True)
        RegistroProntuario.objects.create(id_assistida=cls.maria, id_autor=cls.autora, texto='SIGILOSO')

    def setUp(self):
        self.client.force_login(self.coord)


class AcessoTests(Base):
    def urls(self):
        return [
            reverse('painel_inicio'), reverse('painel_assistidas'), reverse('painel_assistida_nova'),
            reverse('painel_assistida', args=[self.maria.pk]),
            reverse('painel_assistida_editar', args=[self.maria.pk]),
            reverse('painel_assistida_direito', args=[self.maria.pk, 'exportar']),
            reverse('painel_equipe'), reverse('painel_pessoa_adicionar'), reverse('painel_eu_atendo'),
            reverse('painel_pessoa', args=[self.autora.pk]), reverse('painel_pendencias'),
            reverse('painel_atendimentos'), reverse('painel_acessos'),
        ]

    def test_coordenacao_abre_tudo_sem_ver_prontuario(self):
        PendenciaCadastro.objects.create(tipo='assistida', dados={'nome': 'x'})
        Atendimento.objects.create(id_assistida=self.maria, data_atendimento=date(2026, 11, 3), hora_atendimento=time(9))
        for url in self.urls():
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertNotContains(r, 'SIGILOSO')
            self.assertIn('no-store', r['Cache-Control'])

    def test_atendente_recebe_404(self):
        self.client.force_login(self.atendente)
        for url in self.urls():
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_anonimo_vai_para_entrar(self):
        self.client.logout()
        r = self.client.get(reverse('painel_inicio'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/entrar/', r['Location'])

    def test_painel_exige_troca_de_senha(self):
        ContaInterna.objects.filter(usuario=self.coord).update(trocar_senha=True)
        self.assertRedirects(self.client.get(reverse('painel_inicio')), reverse('trocar_senha'))

    def test_coordenacao_cai_no_painel_ao_entrar(self):
        self.client.logout()
        self.coord.set_password('senha-de-teste-1')
        self.coord.save()
        r = self.client.post(reverse('entrar'), {'username': 'coord', 'password': 'senha-de-teste-1'})
        self.assertRedirects(r, reverse('painel_inicio'))

    @override_settings(EXIGIR_2FA=False)
    def test_tela_de_2fa_devolve_cada_um_ao_seu_inicio(self):
        self.assertRedirects(self.client.get(reverse('configurar_2fa')), reverse('painel_inicio'))
        self.client.force_login(self.atendente)
        self.assertRedirects(self.client.get(reverse('configurar_2fa')), reverse('assistidas_lista'))

    def test_atendente_ve_menu_sem_painel(self):
        self.client.force_login(self.atendente)
        self.assertNotContains(self.client.get(reverse('assistidas_lista')), reverse('painel_inicio'))

    def test_painel_nao_abre_prontuario_sem_vinculo(self):
        self.assertEqual(
            self.client.get(reverse('assistida_prontuario', args=[self.maria.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('painel_assistida', args=[self.maria.pk])), 'Abrir prontuário')


class EquipeTests(Base):
    def adicionar(self, **kw):
        return self.client.post(reverse('painel_pessoa_adicionar'), pessoa(**kw))

    def test_um_formulario_cria_tudo_e_a_pessoa_chega_ao_prontuario(self):
        r = self.adicionar()
        self.assertEqual(r.status_code, 200)
        v = Voluntario.objects.get(nomecompleto_voluntario='Lucas Teste')
        self.assertEqual(v.bacharel.cursoformacao_bacharel, 'Psicologia')
        self.assertContains(self.client.get(reverse('painel_equipe')), '<td>Psicologia</td>', html=True)
        self.assertEqual(v.telefone_voluntario, '21999990000')
        self.assertEqual(v.estado_voluntario, 'RJ')
        self.assertEqual(v.usuario.username, 'lucas')
        self.assertTrue(v.usuario.groups.filter(name=GRUPO_ATENDIMENTO).exists())
        self.assertFalse(v.usuario.is_staff)
        self.assertTrue(ContaInterna.objects.get(usuario=v.usuario).trocar_senha)
        senha = r.context['senha']
        self.assertContains(r, senha)
        self.assertIsNotNone(authenticate(r.wsgi_request, username='lucas', password=senha))

        self.client.post(reverse('painel_atendente_adicionar', args=[self.maria.pk]), {'voluntario': v.pk})
        ContaInterna.objects.filter(usuario=v.usuario).update(trocar_senha=False)
        self.client.force_login(v.usuario)
        r = self.client.get(reverse('assistida_prontuario', args=[self.maria.pk]))
        self.assertContains(r, 'SIGILOSO')

    def test_senha_nao_fica_no_banco_em_texto_nem_na_auditoria(self):
        r = self.adicionar()
        self.assertNotIn(r.context['senha'], get_user_model().objects.get(username='lucas').password)
        self.assertEqual(RegistroAcesso.objects.get(acao='usuario_vinculado').login, 'coord')

    def test_login_repetido_ganha_numero(self):
        self.adicionar()
        r = self.adicionar(cpf_voluntario=CPF_B, oab='')
        self.assertEqual(r.context['usuario'].username, 'lucas2')

    def test_advogado_exige_oab_e_nao_repete(self):
        self.assertContains(self.adicionar(funcao='advogado'), 'Informe o número da OAB')
        self.assertContains(self.adicionar(funcao='advogado', oab='RJ000001'), 'já está cadastrada')
        self.assertEqual(self.adicionar(funcao='advogado', oab='RJ999').context['usuario'].username, 'lucas')
        self.assertTrue(Advogado.objects.filter(oab_advogado='RJ999').exists())

    def test_estagiario_exige_curso_e_periodo(self):
        r = self.adicionar(funcao='estagiario')
        self.assertContains(r, 'Informe o curso')
        self.assertContains(r, 'Escolha o período')

    def test_telefone_sem_ddd_e_recusado(self):
        self.assertContains(self.adicionar(telefone_voluntario='99999-0000x1'[:5]), 'Informe o telefone com DDD')

    def test_cpf_repetido_nao_cria_nada(self):
        self.adicionar()
        total = get_user_model().objects.count()
        self.assertContains(self.adicionar(), 'Já existe um cadastro')
        self.assertEqual(get_user_model().objects.count(), total)

    def test_erro_nao_cria_meio_cadastro(self):
        self.adicionar(funcao='advogado')
        self.assertFalse(Voluntario.objects.filter(nomecompleto_voluntario='Lucas Teste').exists())

    def test_coordenacao_marcada_entra_no_grupo_e_no_admin(self):
        usuario = self.adicionar(coordenacao='on').context['usuario']
        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.groups.filter(name=GRUPO_COORDENACAO).exists())

    def test_tambem_vou_atender_usa_o_meu_login(self):
        total = get_user_model().objects.count()
        r = self.client.post(reverse('painel_eu_atendo'), pessoa())
        self.assertRedirects(r, reverse('painel_assistidas'))
        self.assertEqual(get_user_model().objects.count(), total)
        v = Voluntario.objects.get(usuario=self.coord)
        self.client.post(reverse('painel_atendente_adicionar', args=[self.maria.pk]), {'voluntario': v.pk})
        r = self.client.get(reverse('painel_assistida', args=[self.maria.pk]))
        self.assertContains(r, 'Abrir prontuário')

    def test_quem_ja_atende_nao_repete_o_cadastro(self):
        self.client.post(reverse('painel_eu_atendo'), pessoa())
        self.assertRedirects(self.client.get(reverse('painel_eu_atendo')), reverse('painel_equipe'))

    def test_voluntario_do_site_ganha_acesso_com_um_clique(self):
        Voluntario.objects.filter(pk=self.autora.pk).update(usuario=None)
        r = self.client.post(reverse('painel_pessoa_acesso', args=[self.autora.pk, 'criar']))
        self.assertContains(r, r.context['senha'])
        self.autora.refresh_from_db()
        self.assertIsNotNone(self.autora.usuario)

    def test_gerar_nova_senha_obriga_troca_e_audita(self):
        r = self.client.post(reverse('painel_pessoa_acesso', args=[self.autora.pk, 'redefinir']))
        self.assertTrue(ContaInterna.objects.get(usuario=self.atendente).trocar_senha)
        self.assertTrue(RegistroAcesso.objects.filter(acao='senha_redefinida').exists())
        self.assertIsNotNone(authenticate(r.wsgi_request, username='atendente', password=r.context['senha']))

    def test_desativar_e_coordenacao(self):
        self.client.post(reverse('painel_pessoa_acesso', args=[self.autora.pk, 'desativar']))
        self.atendente.refresh_from_db()
        self.assertFalse(self.atendente.is_active)
        self.client.post(reverse('painel_pessoa_acesso', args=[self.autora.pk, 'dar_coordenacao']))
        self.atendente.refresh_from_db()
        self.assertTrue(self.atendente.is_staff)
        self.client.post(reverse('painel_pessoa_acesso', args=[self.autora.pk, 'tirar_coordenacao']))
        self.atendente.refresh_from_db()
        self.assertFalse(self.atendente.is_staff)

    def test_nao_altera_o_proprio_acesso(self):
        Voluntario.objects.filter(pk=self.autora.pk).update(usuario=self.coord)
        for acao in ('desativar', 'tirar_coordenacao'):
            self.client.post(reverse('painel_pessoa_acesso', args=[self.autora.pk, acao]))
        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_active)
        self.assertTrue(self.coord.is_staff)

    def test_coordenacao_nao_mexe_em_superusuario(self):
        Voluntario.objects.filter(pk=self.autora.pk).update(usuario=self.root)
        url = reverse('painel_pessoa_acesso', args=[self.autora.pk, 'redefinir'])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.get(reverse('painel_pessoa', args=[self.autora.pk])).status_code, 404)

    def test_superusuario_nao_aparece_na_lista_da_coordenacao(self):
        Voluntario.objects.filter(pk=self.autora.pk).update(usuario=self.root)
        self.assertNotContains(self.client.get(reverse('painel_equipe')), 'Helena Advogada')

    def test_mudanca_de_acesso_fica_registrada(self):
        for acao in ('desativar', 'dar_coordenacao'):
            self.client.post(reverse('painel_pessoa_acesso', args=[self.autora.pk, acao]))
        self.assertEqual(RegistroAcesso.objects.filter(acao='acesso_alterado', login='coord').count(), 2)

    def test_acao_desconhecida_e_get_nao_passam(self):
        self.assertEqual(self.client.post(reverse('painel_pessoa_acesso', args=[self.autora.pk, 'x'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('painel_pessoa_acesso', args=[self.autora.pk, 'redefinir'])).status_code, 405)

    def test_editar_dados(self):
        dados = pessoa(cpf_voluntario=self.autora.cpf_voluntario, nomecompleto_voluntario='Helena Nova')
        r = self.client.post(reverse('painel_pessoa', args=[self.autora.pk]), dados)
        self.assertEqual(r.status_code, 302)
        self.autora.refresh_from_db()
        self.assertEqual(self.autora.nomecompleto_voluntario, 'Helena Nova')


class AtendentesTests(Base):
    def adicionar(self, voluntario=None):
        return self.client.post(
            reverse('painel_atendente_adicionar', args=[self.maria.pk]),
            {'voluntario': (voluntario or self.autora).pk})

    def test_adicionar_guarda_quem_designou_e_audita(self):
        self.adicionar()
        v = VinculoAtendimento.objects.get()
        self.assertEqual(v.designado_por, self.coord)
        self.assertEqual(RegistroAcesso.objects.get(acao='vinculo_criado').id_assistida, self.maria.pk)

    def test_repetido_nao_duplica(self):
        self.adicionar()
        self.adicionar()
        self.assertEqual(VinculoAtendimento.objects.count(), 1)

    def test_lista_so_tem_quem_tem_acesso(self):
        Voluntario.objects.filter(pk=self.autora.pk).update(usuario=None)
        r = self.client.get(reverse('painel_assistida', args=[self.maria.pk]))
        self.assertNotContains(r, 'Helena Advogada')
        self.adicionar()
        self.assertFalse(VinculoAtendimento.objects.exists())

    def test_encerrar_tira_o_acesso_e_preserva_o_historico(self):
        self.adicionar()
        v = VinculoAtendimento.objects.get()
        self.client.post(reverse('painel_atendente_encerrar', args=[self.maria.pk, v.pk]))
        v.refresh_from_db()
        self.assertIsNotNone(v.fim)
        self.assertTrue(RegistroAcesso.objects.filter(acao='vinculo_encerrado').exists())
        self.client.force_login(self.atendente)
        self.assertEqual(self.client.get(reverse('assistida_prontuario', args=[self.maria.pk])).status_code, 404)


class AssistidasTests(Base):
    def dados(self, **kw):
        return {
            'nome_assistida': 'Nova', 'cpf_assistida': CPF_A, 'idade_assistida': 30, 'cep_assistida': '24020000',
            'rua_assistida': 'Rua', 'num_endereco_assistida': 's/n', 'cidade_assistida': 'Niterói',
            'estado_assistida': 'RJ', **kw,
        }

    def test_nova_leva_a_escolher_atendente(self):
        r = self.client.post(reverse('painel_assistida_nova'), self.dados())
        nova = Assistida.objects.get(nome_assistida='Nova')
        self.assertRedirects(r, reverse('painel_assistida', args=[nova.pk]))

    def test_editar_fica_registrado(self):
        dados = self.dados(cpf_assistida=self.maria.cpf_assistida, nome_assistida='Maria Nova')
        self.client.post(reverse('painel_assistida_editar', args=[self.maria.pk]), dados)
        self.maria.refresh_from_db()
        self.assertEqual(self.maria.nome_assistida, 'Maria Nova')
        self.assertTrue(RegistroAcesso.objects.filter(acao='cadastro_alterado', id_assistida=self.maria.pk).exists())

    def test_cpf_repetido_vira_erro(self):
        criar_assistida(cpf_assistida=CPF_A, nome_assistida='Outra')
        self.assertContains(self.client.post(reverse('painel_assistida_nova'), self.dados()), 'Já existe um cadastro')

    def test_busca_e_filtro_sem_atendente(self):
        joana = criar_assistida(cpf_assistida=CPF_A, nome_assistida='Joana')
        VinculoAtendimento.objects.create(assistida=self.maria, voluntario=self.autora)
        r = self.client.get(reverse('painel_assistidas'), {'filtro': 'sem_atendente'})
        self.assertContains(r, 'Joana')
        self.assertNotContains(r, 'Maria da Silva')
        r = self.client.get(reverse('painel_assistidas'), {'q': CPF_A})
        self.assertContains(r, joana.nome_assistida)
        self.assertNotContains(r, 'Maria da Silva')
        self.assertEqual(self.client.get(reverse('painel_inicio')).context['sem_atendente'], 1)

    def test_lista_nao_mostra_cpf(self):
        self.assertNotContains(self.client.get(reverse('painel_assistidas')), '111.111.111-11')

    def test_get_na_confirmacao_nao_faz_nada(self):
        self.client.get(reverse('painel_assistida_direito', args=[self.maria.pk, 'excluir']))
        self.assertTrue(Assistida.objects.filter(pk=self.maria.pk).exists())
        self.assertFalse(RegistroAcesso.objects.exists())

    def test_exportar_sem_atender_nao_leva_prontuario(self):
        r = self.client.post(reverse('painel_assistida_direito', args=[self.maria.pk, 'exportar']))
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertNotIn('SIGILOSO', r.content.decode())
        self.assertTrue(RegistroAcesso.objects.filter(acao='exportacao').exists())

    def test_anonimizar_e_depois_nao_edita(self):
        self.client.post(reverse('painel_assistida_direito', args=[self.maria.pk, 'anonimizar']))
        a = Assistida.objects.get(pk=self.maria.pk)
        self.assertTrue(a.anonimizada)
        self.assertEqual(self.client.get(reverse('painel_assistida_editar', args=[a.pk])).status_code, 404)
        self.assertContains(self.client.get(reverse('painel_assistida', args=[a.pk])), 'Cadastro anonimizado')

    def test_excluir(self):
        self.client.post(reverse('painel_assistida_direito', args=[self.maria.pk, 'excluir']))
        self.assertFalse(Assistida.objects.filter(pk=self.maria.pk).exists())
        self.assertTrue(RegistroAcesso.objects.filter(acao='exclusao').exists())

    def test_direito_desconhecido_da_404(self):
        self.assertEqual(self.client.get(reverse('painel_assistida_direito', args=[self.maria.pk, 'x'])).status_code, 404)


class DemaisTelasTests(Base):
    def test_resolver_pendencia(self):
        p = PendenciaCadastro.objects.create(tipo='assistida', dados={'nome': 'Fulana'})
        self.assertContains(self.client.get(reverse('painel_pendencias')), 'Fulana')
        self.client.post(reverse('painel_pendencia_resolver', args=[p.pk]))
        self.assertNotContains(self.client.get(reverse('painel_pendencias')), 'Fulana')

    def test_agendar_e_cancelar(self):
        self.client.post(reverse('painel_atendimentos'), {
            'id_assistida': self.maria.pk, 'data_atendimento': '2026-11-03', 'hora_atendimento': '09:00'})
        a = Atendimento.objects.get()
        self.assertContains(self.client.get(reverse('painel_atendimentos')), '03/11/2026')
        self.client.post(reverse('painel_atendimento_cancelar', args=[a.pk]))
        self.assertFalse(Atendimento.objects.exists())

    def test_acessos_filtra_e_nao_altera(self):
        RegistroAcesso.objects.create(login='ana', acao='leitura')
        RegistroAcesso.objects.create(login='bia', acao='negacao')
        r = self.client.get(reverse('painel_acessos'), {'acao': 'negacao'})
        self.assertContains(r, 'bia')
        self.assertNotContains(r, 'ana')
