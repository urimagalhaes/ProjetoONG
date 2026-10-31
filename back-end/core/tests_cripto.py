from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import FieldError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from assistidas.models import (
    Assistida, PendenciaCadastro, RegistroAcesso, RegistroProntuario, RegistroProntuarioVersao,
    VinculoAtendimento,
)
from assistidas.tests import criar_advogada, criar_assistida, criar_login
from core.cripto import cifrar, decifrar, hash_cpf
from core.utils_teste import STORAGES_TESTE
from voluntarios.models import Voluntario


def valor_bruto(tabela, coluna, pk_coluna, pk):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT "{coluna}" FROM "{tabela}" WHERE "{pk_coluna}" = %s', [pk])
        return cursor.fetchone()[0]


class ChavesTests(SimpleTestCase):
    def test_troca_de_chave_ainda_le_o_que_foi_cifrado_com_a_antiga(self):
        antiga, nova = Fernet.generate_key().decode(), Fernet.generate_key().decode()
        with override_settings(CHAVES_CIFRAGEM=[antiga]):
            token = cifrar('dado')
        with override_settings(CHAVES_CIFRAGEM=[nova, antiga]):
            self.assertEqual(decifrar(token), 'dado')

    def test_chave_errada_nao_le(self):
        token = cifrar('dado')
        with override_settings(CHAVES_CIFRAGEM=[Fernet.generate_key().decode()]):
            with self.assertRaises(InvalidToken):
                decifrar(token)

    def test_hash_ignora_mascara_e_depende_da_chave(self):
        self.assertEqual(hash_cpf('529.982.247-25'), hash_cpf('52998224725'))
        with override_settings(CHAVE_HASH_CPF='outra'):
            outro = hash_cpf('52998224725')
        self.assertNotEqual(outro, hash_cpf('52998224725'))


class DadosCifradosNoBancoTests(TestCase):
    def test_assistida_fica_ilegivel_no_banco_e_legivel_no_python(self):
        a = criar_assistida(telefone_assistida='21999990000')
        for coluna, legivel in (('cpf_assistida', '111.111.111-11'), ('telefone_assistida', '21999990000'),
                                ('rua_assistida', 'Rua A'), ('cep_assistida', '24020000')):
            bruto = valor_bruto('Assistidas', coluna, 'id_assistida', a.pk)
            self.assertNotIn(legivel, bruto)
            self.assertTrue(bruto.startswith('gAAAA'), coluna)
        self.assertEqual(Assistida.objects.get(pk=a.pk).cpf_assistida, '111.111.111-11')
        self.assertEqual(valor_bruto('Assistidas', 'nome_assistida', 'id_assistida', a.pk), 'Maria da Silva')

    def test_voluntario_fica_ilegivel(self):
        v = criar_advogada()
        for coluna in ('cpf_voluntario', 'rg_voluntario', 'telefone_voluntario', 'endereco_voluntario'):
            self.assertTrue(valor_bruto('Voluntarios', coluna, 'id_voluntario', v.pk).startswith('gAAAA'))

    def test_texto_do_prontuario_fica_ilegivel(self):
        r = RegistroProntuario.objects.create(
            id_assistida=criar_assistida(), id_autor=criar_advogada(), texto='SIGILOSO')
        self.assertNotIn('SIGILOSO', valor_bruto('RegistrosProntuario', 'texto', 'id_registro', r.pk))
        self.assertEqual(RegistroProntuario.objects.get(pk=r.pk).texto, 'SIGILOSO')

    def test_pendencia_fica_ilegivel(self):
        p = PendenciaCadastro.objects.create(tipo='assistida', dados={'nome': 'Maria'})
        self.assertNotIn('Maria', valor_bruto('PendenciasCadastro', 'dados', 'id_pendencia', p.pk))
        self.assertEqual(PendenciaCadastro.objects.get(pk=p.pk).dados, {'nome': 'Maria'})

    def test_mesmo_cpf_gera_textos_diferentes(self):
        a = criar_assistida()
        b = criar_assistida(cpf_assistida='222.222.222-22')
        self.assertNotEqual(a.cpf_hash, b.cpf_hash)
        self.assertNotEqual(cifrar('x'), cifrar('x'))

    def test_cpf_repetido_e_barrado_pelo_hash(self):
        criar_assistida()
        with self.assertRaises(IntegrityError), transaction.atomic():
            criar_assistida()

    def test_filtrar_por_campo_cifrado_avisa_em_vez_de_voltar_vazio(self):
        with self.assertRaises(FieldError):
            Assistida.objects.filter(cpf_assistida='111.111.111-11').exists()
        with self.assertRaises(FieldError):
            Assistida.objects.filter(cpf_assistida__icontains='111').exists()

    def test_tamanho_maximo_continua_validado(self):
        a = criar_assistida()
        a.telefone_assistida = '1' * 12
        with self.assertRaises(Exception) as erro:
            a.full_clean(validate_unique=False)
        self.assertIn('telefone_assistida', erro.exception.message_dict)


@override_settings(STORAGES=STORAGES_TESTE)
class AuditoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maria = criar_assistida()
        cls.autora = criar_advogada()
        cls.url = reverse('assistida_prontuario', args=[cls.maria.pk])

    def test_leitura_fica_registrada_sem_conteudo(self):
        usuario = criar_login('a', self.autora)
        VinculoAtendimento.objects.create(assistida=self.maria, voluntario=self.autora)
        self.client.force_login(usuario)
        self.client.get(self.url, HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1')
        acesso = RegistroAcesso.objects.get()
        self.assertEqual(acesso.acao, 'leitura')
        self.assertEqual(acesso.login, 'a')
        self.assertEqual(acesso.id_assistida, self.maria.pk)
        self.assertEqual(acesso.ip, '203.0.113.9')

    def test_negacao_fica_registrada(self):
        self.client.force_login(criar_login('b'))
        self.client.get(self.url)
        self.assertEqual(RegistroAcesso.objects.get().acao, 'negacao')

    def test_ip_invalido_nao_derruba_a_pagina(self):
        self.client.force_login(criar_login('b'))
        self.assertEqual(self.client.get(self.url, HTTP_X_FORWARDED_FOR='lixo').status_code, 404)
        self.assertIsNone(RegistroAcesso.objects.get().ip)

    def test_registro_sobrevive_a_exclusao_da_assistida_e_do_usuario(self):
        usuario = criar_login('b')
        self.client.force_login(usuario)
        self.client.get(self.url)
        self.maria.delete()
        usuario.delete()
        acesso = RegistroAcesso.objects.get()
        self.assertIsNone(acesso.usuario)
        self.assertEqual(acesso.login, 'b')

    def test_nao_pode_alterar_nem_apagar(self):
        acesso = RegistroAcesso.objects.create(login='x', acao='leitura')
        with self.assertRaises(TypeError):
            acesso.save()
        with self.assertRaises(TypeError):
            acesso.delete()
        with self.assertRaises(TypeError):
            RegistroAcesso.objects.all().delete()
        with self.assertRaises(TypeError):
            RegistroAcesso.objects.update(login='y')

    def test_versao_guarda_texto_cifrado(self):
        r = RegistroProntuario.objects.create(id_assistida=self.maria, id_autor=self.autora, texto='novo')
        v = RegistroProntuarioVersao.objects.create(registro=r, texto_anterior='ANTIGO')
        self.assertNotIn('ANTIGO', valor_bruto(
            'RegistrosProntuarioVersoes', 'texto_anterior', 'id_versao', v.pk))


class MigracaoDeCriptografiaTests(TransactionTestCase):
    """Dados que já existem precisam ser cifrados, e a reversão precisa devolvê-los."""

    antes = [('assistidas', '0004_vinculoatendimento'), ('voluntarios', '0010_voluntario_usuario')]
    depois = [('assistidas', '0005_criptografia_e_auditoria'), ('voluntarios', '0011_criptografia')]

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.migrate(alvo)
        return MigrationExecutor(connection).loader.project_state(alvo).apps

    def tearDown(self):
        self.migrar(self.depois)

    def test_cifra_e_reverte(self):
        apps = self.migrar(self.antes)
        a = apps.get_model('assistidas', 'Assistida').objects.create(
            cpf_assistida='111.111.111-11', nome_assistida='Maria', cep_assistida='24020000', idade_assistida=30,
            cidade_assistida='Niterói', estado_assistida='RJ', rua_assistida='Rua A',
            num_endereco_assistida='s/n', telefone_assistida='21999990000')
        v = apps.get_model('voluntarios', 'Voluntario').objects.create(
            email_voluntario='h@example.com', nomecompleto_voluntario='Helena', datanasc_voluntario='1990-01-01',
            sexo_voluntario='F', cidade_voluntario='Niterói', estado_voluntario='RJ', endereco_voluntario='Rua B',
            telefone_voluntario='999990000', cpf_voluntario='000.000.000-01', rg_voluntario='123456789')
        r = apps.get_model('assistidas', 'RegistroProntuario').objects.create(
            id_assistida_id=a.pk, id_autor_id=v.pk, texto='SIGILOSO')
        p = apps.get_model('assistidas', 'PendenciaCadastro').objects.create(tipo='assistida', dados={'nome': 'Ana'})

        self.migrar(self.depois)
        self.assertTrue(valor_bruto('Assistidas', 'cpf_assistida', 'id_assistida', a.pk).startswith('gAAAA'))
        self.assertTrue(valor_bruto('Voluntarios', 'rg_voluntario', 'id_voluntario', v.pk).startswith('gAAAA'))
        self.assertTrue(valor_bruto('RegistrosProntuario', 'texto', 'id_registro', r.pk).startswith('gAAAA'))
        self.assertEqual(Assistida.objects.get(pk=a.pk).cpf_hash, hash_cpf('111.111.111-11'))
        self.assertEqual(Voluntario.objects.get(pk=v.pk).rg_voluntario, '123456789')
        self.assertEqual(RegistroProntuario.objects.get(pk=r.pk).texto, 'SIGILOSO')
        self.assertEqual(PendenciaCadastro.objects.get(pk=p.pk).dados, {'nome': 'Ana'})

        self.migrar(self.antes)
        self.assertEqual(valor_bruto('Assistidas', 'cpf_assistida', 'id_assistida', a.pk), '111.111.111-11')
        self.assertEqual(valor_bruto('Assistidas', 'telefone_assistida', 'id_assistida', a.pk), '21999990000')
        self.assertEqual(valor_bruto('Voluntarios', 'rg_voluntario', 'id_voluntario', v.pk), '123456789')
        self.assertEqual(valor_bruto('RegistrosProntuario', 'texto', 'id_registro', r.pk), 'SIGILOSO')
