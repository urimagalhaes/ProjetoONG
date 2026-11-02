import json
from datetime import date, time

from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from atendimentos.models import Atendimento
from core.models import ContaInterna
from core.utils_teste import STORAGES_TESTE
from voluntarios.models import Voluntario
from .models import (
    Assistida, PendenciaCadastro, RegistroAcesso, RegistroProntuario, RegistroProntuarioVersao,
    VinculoAtendimento,
)
from .permissoes import GRUPO_ATENDIMENTO, GRUPO_COORDENACAO
from .tests import criar_advogada, criar_assistida, criar_login

CPF_VALIDO = '529.982.247-25'


@override_settings(STORAGES=STORAGES_TESTE)
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maria = criar_assistida()
        cls.autora = criar_advogada()
        cls.atendente = criar_login('atendente', cls.autora)
        cls.vinculo = VinculoAtendimento.objects.create(assistida=cls.maria, voluntario=cls.autora)
        cls.registro = RegistroProntuario.objects.create(
            id_assistida=cls.maria, id_autor=cls.autora, texto='SIGILOSO')
        cls.coordenadora = criar_login('coord', is_staff=True)
        cls.coordenadora.groups.add(Group.objects.get(name=GRUPO_COORDENACAO))
        cls.root = criar_login('root', is_staff=True, is_superuser=True)


class RegistroTests(Base):
    def url_novo(self, assistida=None):
        return reverse('registro_novo', args=[(assistida or self.maria).pk])

    def url_editar(self, registro=None, assistida=None):
        return reverse('registro_editar', args=[(assistida or self.maria).pk, (registro or self.registro).pk])

    def test_novo_registro_usa_o_autor_do_login(self):
        outra = Voluntario.objects.create(
            email_voluntario='o@example.com', nomecompleto_voluntario='Outra',
            datanasc_voluntario=date(1990, 1, 1), sexo_voluntario='F', cidade_voluntario='Niterói',
            estado_voluntario='RJ', endereco_voluntario='Rua', telefone_voluntario='999990000',
            instagram_voluntario='@o', cpf_voluntario='000.000.000-02', rg_voluntario='1')
        self.client.force_login(self.atendente)
        r = self.client.post(self.url_novo(), {
            'texto': 'novo', 'id_autor': outra.pk, 'id_assistida': 9999})
        self.assertRedirects(r, reverse('assistida_prontuario', args=[self.maria.pk]))
        novo = RegistroProntuario.objects.exclude(pk=self.registro.pk).get()
        self.assertEqual(novo.id_autor, self.autora)
        self.assertEqual(novo.id_assistida, self.maria)
        acesso = RegistroAcesso.objects.get(acao='criacao')
        self.assertEqual((acesso.id_assistida, acesso.id_registro), (self.maria.pk, novo.pk))

    def test_texto_vazio_nao_grava(self):
        self.client.force_login(self.atendente)
        self.assertEqual(self.client.post(self.url_novo(), {'texto': '   '}).status_code, 200)
        self.assertEqual(RegistroProntuario.objects.count(), 1)

    def test_sem_vinculo_nao_escreve(self):
        self.client.force_login(self.coordenadora)
        self.assertEqual(self.client.post(self.url_novo(), {'texto': 'x'}).status_code, 404)
        self.client.force_login(self.root)
        self.assertEqual(self.client.post(self.url_novo(), {'texto': 'x'}).status_code, 404)
        self.assertEqual(RegistroProntuario.objects.count(), 1)
        self.assertEqual(RegistroAcesso.objects.filter(acao='negacao').count(), 2)

    def test_csrf_e_exigido(self):
        from django.test import Client
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.atendente)
        self.assertEqual(cliente.post(self.url_novo(), {'texto': 'x'}).status_code, 403)

    def test_edicao_guarda_versao_e_audita(self):
        self.client.force_login(self.atendente)
        self.client.post(self.url_editar(), {'texto': 'corrigido'})
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.texto, 'corrigido')
        versao = RegistroProntuarioVersao.objects.get()
        self.assertEqual(versao.texto_anterior, 'SIGILOSO')
        self.assertEqual(versao.editado_por, self.atendente)
        self.assertEqual(RegistroAcesso.objects.get(acao='edicao').id_registro, self.registro.pk)

    def test_salvar_sem_mudar_nao_cria_versao(self):
        self.client.force_login(self.atendente)
        self.client.post(self.url_editar(), {'texto': 'SIGILOSO'})
        self.assertFalse(RegistroProntuarioVersao.objects.exists())

    def test_so_o_autor_edita(self):
        colega = Voluntario.objects.create(
            email_voluntario='c@example.com', nomecompleto_voluntario='Colega',
            datanasc_voluntario=date(1990, 1, 1), sexo_voluntario='F', cidade_voluntario='Niterói',
            estado_voluntario='RJ', endereco_voluntario='Rua', telefone_voluntario='999990000',
            instagram_voluntario='@c', cpf_voluntario='000.000.000-03', rg_voluntario='1')
        login = criar_login('colega', colega)
        VinculoAtendimento.objects.create(assistida=self.maria, voluntario=colega)
        self.client.force_login(login)
        r = self.client.get(reverse('assistida_prontuario', args=[self.maria.pk]))
        self.assertContains(r, 'SIGILOSO')
        self.assertNotContains(r, self.url_editar())
        self.assertEqual(self.client.post(self.url_editar(), {'texto': 'x'}).status_code, 404)
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.texto, 'SIGILOSO')

    def test_autora_com_vinculo_encerrado_nao_edita(self):
        VinculoAtendimento.objects.filter(pk=self.vinculo.pk).update(fim=timezone.now())
        self.client.force_login(self.atendente)
        self.assertEqual(self.client.post(self.url_editar(), {'texto': 'x'}).status_code, 404)

    def test_registro_de_outra_assistida_na_url_da_404(self):
        joana = criar_assistida(cpf_assistida='222.222.222-22', nome_assistida='Joana')
        VinculoAtendimento.objects.create(assistida=joana, voluntario=self.autora)
        self.client.force_login(self.atendente)
        self.assertEqual(self.client.get(self.url_editar(assistida=joana)).status_code, 404)

    def test_atendente_nao_ve_link_de_editar_cadastro(self):
        self.client.force_login(self.atendente)
        r = self.client.get(reverse('assistida_prontuario', args=[self.maria.pk]))
        self.assertNotContains(r, 'Ver cadastro')
        self.assertNotContains(r, '/admin/')

    def test_atendente_nao_entra_no_admin(self):
        self.client.force_login(self.atendente)
        r = self.client.get(reverse('admin:assistidas_assistida_change', args=[self.maria.pk]))
        self.assertEqual(r.status_code, 302)


class AdminSemProntuarioTests(Base):
    def test_nenhuma_tela_mostra_o_texto(self):
        PendenciaCadastro.objects.create(tipo='assistida', dados={'nome': 'x'})
        VinculoAtendimento.objects.create(assistida=self.maria, voluntario=self.autora, fim=timezone.now())
        self.client.force_login(self.root)
        for modelo in admin.site._registry:
            info = f'{modelo._meta.app_label}_{modelo._meta.model_name}'
            r = self.client.get(reverse(f'admin:{info}_changelist'))
            self.assertEqual(r.status_code, 200, info)
            self.assertNotContains(r, 'SIGILOSO')
            for objeto in modelo._default_manager.all()[:3]:
                r = self.client.get(reverse(f'admin:{info}_change', args=[objeto.pk]))
                self.assertEqual(r.status_code, 200, info)
                self.assertNotContains(r, 'SIGILOSO')

    def test_prontuario_nao_tem_rota_no_admin(self):
        for nome in ('assistidas_registroprontuario_changelist', 'assistidas_registroprontuarioversao_changelist'):
            with self.assertRaises(NoReverseMatch):
                reverse(f'admin:{nome}')

    def test_cpf_fora_da_listagem(self):
        self.client.force_login(self.coordenadora)
        r = self.client.get(reverse('admin:assistidas_assistida_changelist'))
        self.assertContains(r, 'Maria da Silva')
        self.assertNotContains(r, '111.111.111-11')

    def test_coordenacao_abre_as_telas_do_dia_a_dia(self):
        self.client.force_login(self.coordenadora)
        for nome in ('assistidas_assistida', 'assistidas_pendenciacadastro', 'assistidas_vinculoatendimento',
                     'assistidas_registroacesso', 'voluntarios_voluntario', 'atendimentos_atendimento',
                     'auth_user'):
            self.assertEqual(self.client.get(reverse(f'admin:{nome}_changelist')).status_code, 200, nome)

    def test_coordenacao_nao_ve_otp(self):
        self.client.force_login(self.coordenadora)
        self.assertEqual(self.client.get(reverse('admin:otp_totp_totpdevice_changelist')).status_code, 403)


class CadastroNoAdminTests(Base):
    def dados(self, **kw):
        a = self.maria
        return {
            'nome_assistida': a.nome_assistida, 'cpf_assistida': a.cpf_assistida,
            'idade_assistida': a.idade_assistida, 'cep_assistida': a.cep_assistida,
            'rua_assistida': a.rua_assistida, 'num_endereco_assistida': a.num_endereco_assistida,
            'cidade_assistida': a.cidade_assistida, 'estado_assistida': a.estado_assistida, **kw,
        }

    def post(self, **kw):
        self.client.force_login(self.coordenadora)
        return self.client.post(
            reverse('admin:assistidas_assistida_change', args=[self.maria.pk]), self.dados(**kw))

    def test_cadastro_antigo_com_cpf_fora_do_padrao_pode_ser_editado(self):
        self.assertEqual(self.post(rua_assistida='Rua Nova').status_code, 302)
        self.assertEqual(Assistida.objects.get(pk=self.maria.pk).rua_assistida, 'Rua Nova')

    def test_cpf_invalido_e_recusado(self):
        self.assertContains(self.post(cpf_assistida='123'), 'CPF inválido')

    def test_cpf_repetido_vira_erro_de_formulario(self):
        criar_assistida(cpf_assistida=CPF_VALIDO, nome_assistida='Outra')
        self.assertContains(self.post(cpf_assistida=CPF_VALIDO), 'Já existe um cadastro')

    def test_cpf_novo_atualiza_o_hash(self):
        self.post(cpf_assistida='52998224725')
        a = Assistida.objects.get(pk=self.maria.pk)
        self.assertEqual(a.cpf_assistida, CPF_VALIDO)
        self.assertNotEqual(a.cpf_hash, self.maria.cpf_hash)

    def test_ninguem_apaga_assistida_pela_tela_padrao(self):
        self.client.force_login(self.root)
        r = self.client.get(reverse('admin:assistidas_assistida_delete', args=[self.maria.pk]))
        self.assertEqual(r.status_code, 403)


class VinculoNoAdminTests(Base):
    url_add = 'admin:assistidas_vinculoatendimento_add'

    def setUp(self):
        self.client.force_login(self.coordenadora)
        self.joana = criar_assistida(cpf_assistida='222.222.222-22', nome_assistida='Joana')

    def test_designado_por_vem_do_login_e_fica_auditado(self):
        r = self.client.post(reverse(self.url_add), {
            'assistida': self.joana.pk, 'voluntario': self.autora.pk, 'designado_por': self.root.pk})
        self.assertEqual(r.status_code, 302)
        vinculo = VinculoAtendimento.objects.get(assistida=self.joana)
        self.assertEqual(vinculo.designado_por, self.coordenadora)
        self.assertEqual(RegistroAcesso.objects.get(acao='vinculo_criado').id_assistida, self.joana.pk)

    def test_vinculo_ativo_repetido_vira_erro_de_formulario(self):
        r = self.client.post(reverse(self.url_add), {'assistida': self.maria.pk, 'voluntario': self.autora.pk})
        self.assertContains(r, 'já tem vínculo ativo')
        self.assertEqual(VinculoAtendimento.objects.count(), 1)

    def test_encerrar_preserva_historico_e_audita(self):
        self.client.post(reverse('admin:assistidas_vinculoatendimento_changelist'), {
            'action': 'encerrar', '_selected_action': [self.vinculo.pk]})
        self.vinculo.refresh_from_db()
        self.assertIsNotNone(self.vinculo.fim)
        self.assertEqual(RegistroAcesso.objects.filter(acao='vinculo_encerrado').count(), 1)

    def test_vinculo_nao_muda_de_assistida_nem_e_apagado(self):
        self.client.post(reverse('admin:assistidas_vinculoatendimento_change', args=[self.vinculo.pk]), {
            'assistida': self.joana.pk, 'voluntario': self.autora.pk})
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.assistida, self.maria)
        self.client.force_login(self.root)
        r = self.client.get(reverse('admin:assistidas_vinculoatendimento_delete', args=[self.vinculo.pk]))
        self.assertEqual(r.status_code, 403)


class RegistroAcessoNoAdminTests(Base):
    def test_e_so_leitura_inclusive_para_superusuario(self):
        acesso = RegistroAcesso.objects.create(login='x', acao='leitura')
        self.client.force_login(self.root)
        self.assertEqual(self.client.get(reverse('admin:assistidas_registroacesso_add')).status_code, 403)
        url = reverse('admin:assistidas_registroacesso_delete', args=[acesso.pk])
        self.assertEqual(self.client.post(url, {'post': 'yes'}).status_code, 403)
        url = reverse('admin:assistidas_registroacesso_change', args=[acesso.pk])
        self.assertEqual(self.client.post(url, {'login': 'y'}).status_code, 403)


class UsuariosNoAdminTests(Base):
    def setUp(self):
        self.client.force_login(self.coordenadora)

    def salvar(self, usuario, **kw):
        dados = {'username': usuario.username, 'is_active': 'on', **kw}
        return self.client.post(reverse('admin:auth_user_change', args=[usuario.pk]), dados)

    def test_superusuario_fica_invisivel(self):
        self.assertNotContains(self.client.get(reverse('admin:auth_user_changelist')), '>root<')
        url = reverse('admin:auth_user_change', args=[self.root.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        url = reverse('admin:auth_user_password_change', args=[self.root.pk])
        self.assertEqual(self.client.post(url, {'password1': 'x', 'password2': 'x'}).status_code, 404)

    def test_nao_escala_privilegio(self):
        self.salvar(self.atendente, is_superuser='on', is_staff='on')
        self.atendente.refresh_from_db()
        self.assertFalse(self.atendente.is_superuser)
        self.assertFalse(self.atendente.is_staff)

    def test_so_oferece_os_dois_grupos(self):
        Group.objects.create(name='Outro')
        r = self.client.get(reverse('admin:auth_user_change', args=[self.atendente.pk]))
        self.assertContains(r, GRUPO_ATENDIMENTO)
        self.assertNotContains(r, 'Outro')
        self.assertNotContains(r, 'user_permissions')

    def test_entrada_no_admin_segue_o_grupo(self):
        grupo = Group.objects.get(name=GRUPO_COORDENACAO)
        self.assertEqual(self.salvar(self.atendente, groups=[grupo.pk]).status_code, 302)
        self.atendente.refresh_from_db()
        self.assertTrue(self.atendente.is_staff)
        self.salvar(self.atendente)
        self.atendente.refresh_from_db()
        self.assertFalse(self.atendente.is_staff)

    def test_redefinir_senha_obriga_troca_e_audita(self):
        url = reverse('admin:auth_user_password_change', args=[self.atendente.pk])
        r = self.client.post(url, {'password1': 'SenhaNova!2026x', 'password2': 'SenhaNova!2026x',
                                   'usable_password': 'true'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ContaInterna.objects.get(usuario=self.atendente).trocar_senha)
        self.assertTrue(RegistroAcesso.objects.filter(acao='senha_redefinida', login='coord').exists())

    def test_login_novo_precisa_trocar_a_senha(self):
        r = self.client.post(reverse('admin:auth_user_add'), {
            'username': 'nova', 'usable_password': 'true',
            'password1': 'SenhaNova!2026x', 'password2': 'SenhaNova!2026x'})
        self.assertEqual(r.status_code, 302)
        nova = get_user_model().objects.get(username='nova')
        self.client.force_login(nova)
        self.assertRedirects(self.client.get(reverse('assistidas_lista')), reverse('trocar_senha'))

    def test_ligar_login_a_voluntario_e_auditado(self):
        livre = criar_login('livre')
        v = self.autora
        dados = {
            'nomecompleto_voluntario': v.nomecompleto_voluntario, 'email_voluntario': v.email_voluntario,
            'datanasc_voluntario': '1990-01-01', 'sexo_voluntario': v.sexo_voluntario,
            'cpf_voluntario': v.cpf_voluntario, 'rg_voluntario': v.rg_voluntario,
            'endereco_voluntario': v.endereco_voluntario, 'cidade_voluntario': v.cidade_voluntario,
            'estado_voluntario': v.estado_voluntario, 'telefone_voluntario': v.telefone_voluntario,
            'instagram_voluntario': v.instagram_voluntario, 'usuario': livre.pk,
        }
        r = self.client.post(reverse('admin:voluntarios_voluntario_change', args=[v.pk]), dados)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Voluntario.objects.get(pk=v.pk).usuario, livre)
        self.assertTrue(RegistroAcesso.objects.filter(acao='usuario_vinculado').exists())


class DireitosDaTitularTests(Base):
    url = 'admin:assistidas_assistida_changelist'

    def acao(self, nome, *ids, confirmado=True):
        dados = {'action': nome, '_selected_action': list(ids) or [self.maria.pk]}
        if confirmado:
            dados['confirmado'] = '1'
        return self.client.post(reverse(self.url), dados)

    def test_sem_confirmar_nao_faz_nada(self):
        self.client.force_login(self.coordenadora)
        for nome in ('exportar_dados', 'anonimizar', 'excluir_definitivamente'):
            r = self.acao(nome, confirmado=False)
            self.assertContains(r, 'name="confirmado"')
        self.assertTrue(Assistida.objects.filter(pk=self.maria.pk, nome_assistida='Maria da Silva').exists())
        self.assertFalse(RegistroAcesso.objects.exists())

    def test_uma_por_vez(self):
        outra = criar_assistida(cpf_assistida='222.222.222-22', nome_assistida='Outra')
        self.client.force_login(self.coordenadora)
        self.acao('excluir_definitivamente', self.maria.pk, outra.pk)
        self.assertEqual(Assistida.objects.count(), 2)

    def test_exportar_sem_vinculo_nao_leva_o_prontuario(self):
        self.client.force_login(self.coordenadora)
        r = self.acao('exportar_dados')
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertIn('no-store', r['Cache-Control'])
        dados = json.loads(r.content)
        self.assertEqual(dados['cadastro']['cpf'], '111.111.111-11')
        self.assertIs(dados['prontuario_incluido'], False)
        self.assertNotIn('SIGILOSO', r.content.decode())
        self.assertEqual(RegistroAcesso.objects.get(acao='exportacao').id_assistida, self.maria.pk)

    def test_exportar_com_vinculo_leva_prontuario_e_versoes(self):
        self.autora.usuario = self.coordenadora
        self.autora.save()
        RegistroProntuarioVersao.objects.create(registro=self.registro, texto_anterior='ANTES')
        self.client.force_login(self.coordenadora)
        dados = json.loads(self.acao('exportar_dados').content)
        self.assertEqual(dados['prontuario'][0]['texto'], 'SIGILOSO')
        self.assertEqual(dados['prontuario'][0]['versoes_anteriores'][0]['texto'], 'ANTES')

    def preparar_copias(self):
        PendenciaCadastro.objects.create(tipo='assistida', dados={'cpf': '111.111.111-11', 'nome': 'Maria'})
        self.outra = PendenciaCadastro.objects.create(tipo='assistida', dados={'cpf': CPF_VALIDO})
        LogEntry.objects.create(
            user=self.coordenadora, content_type=ContentType.objects.get_for_model(Assistida),
            object_id=str(self.maria.pk), object_repr='Maria da Silva', action_flag=CHANGE)

    def test_anonimizar_limpa_e_encerra(self):
        self.preparar_copias()
        Atendimento.objects.create(id_assistida=self.maria, data_atendimento=date(2026, 11, 3), hora_atendimento=time(9))
        self.client.force_login(self.coordenadora)
        self.acao('anonimizar')
        a = Assistida.objects.get(pk=self.maria.pk)
        self.assertEqual(a.nome_assistida, f'Anônima #{a.pk}')
        self.assertEqual(a.cpf_assistida, '')
        self.assertEqual(a.rua_assistida, '')
        self.assertEqual(a.telefone_assistida, '')
        self.assertEqual(a.cidade_assistida, '')
        self.assertTrue(a.anonimizada)
        self.assertFalse(RegistroProntuario.objects.exists())
        self.assertFalse(VinculoAtendimento.objects.filter(fim__isnull=True).exists())
        self.assertEqual(list(PendenciaCadastro.objects.all()), [self.outra])
        self.assertFalse(LogEntry.objects.exists())
        self.assertEqual(RegistroAcesso.objects.get(acao='anonimizacao').id_assistida, a.pk)

    def test_anonimizada_libera_o_cpf_e_nao_pode_ser_editada(self):
        self.client.force_login(self.coordenadora)
        self.acao('anonimizar')
        criar_assistida()
        r = self.client.post(reverse('admin:assistidas_assistida_change', args=[self.maria.pk]), {})
        self.assertEqual(r.status_code, 403)

    def test_excluir_apaga_tudo_e_mantem_a_auditoria(self):
        self.preparar_copias()
        id_maria = self.maria.pk
        self.client.force_login(self.coordenadora)
        self.acao('excluir_definitivamente')
        self.assertFalse(Assistida.objects.filter(pk=id_maria).exists())
        self.assertFalse(RegistroProntuario.objects.exists())
        self.assertFalse(VinculoAtendimento.objects.exists())
        self.assertEqual(list(PendenciaCadastro.objects.all()), [self.outra])
        self.assertFalse(LogEntry.objects.exists())
        self.assertEqual(RegistroAcesso.objects.get(acao='exclusao').id_assistida, id_maria)
