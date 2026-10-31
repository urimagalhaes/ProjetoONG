import json
import os
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.utils_teste import STORAGES_TESTE
from services import cpf_valido

PASTA_CORE = Path(settings.BASE_DIR) / 'core'
PAGINAS_COM_FORMULARIO = (
    'cadastro_assistida', 'voluntario_advogado', 'voluntario_bacharel', 'voluntario_estagiario',
)


class ConfiguracaoProducaoTests(SimpleTestCase):
    """Carrega o settings num processo novo, como a hospedagem faz."""

    NOMES = [
        'SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE', 'SECURE_HSTS_SECONDS',
        'SESSION_COOKIE_AGE', 'SESSION_EXPIRE_AT_BROWSER_CLOSE', 'CSRF_TRUSTED_ORIGINS',
    ]

    def executar(self, **env):
        codigo = (
            'import json, django; django.setup(); from django.conf import settings as s; '
            f'print(json.dumps({{n: getattr(s, n) for n in {self.NOMES!r}}} | '
            '{"db": {k: s.DATABASES["default"].get(k) for k in '
            '("CONN_MAX_AGE", "DISABLE_SERVER_SIDE_CURSORS", "OPTIONS")}}, default=str))'
        )
        ambiente = {
            **os.environ, 'DJANGO_SETTINGS_MODULE': 'server.settings', 'SECRET_KEY': 'x' * 60,
            'DEBUG': 'False', 'DATABASE_URL': 'postgres://u:s@exemplo.invalid:6543/banco',
            'DB_SSL': 'True',
            'CHAVES_CIFRAGEM': Fernet.generate_key().decode(), 'CHAVE_HASH_CPF': 'y' * 40, **env,
        }
        return subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True,
                              env=ambiente, cwd=settings.BASE_DIR)

    def carregar(self, **env):
        saida = self.executar(**env)
        self.assertEqual(saida.returncode, 0, saida.stderr)
        return json.loads(saida.stdout)

    def test_producao_exige_https_e_cookies_seguros(self):
        c = self.carregar(CSRF_TRUSTED_ORIGINS='https://a.example, https://b.example')
        self.assertTrue(c['SECURE_SSL_REDIRECT'])
        self.assertTrue(c['SESSION_COOKIE_SECURE'])
        self.assertTrue(c['CSRF_COOKIE_SECURE'])
        self.assertGreater(c['SECURE_HSTS_SECONDS'], 0)
        self.assertEqual(c['SESSION_COOKIE_AGE'], 3600)
        self.assertTrue(c['SESSION_EXPIRE_AT_BROWSER_CLOSE'])
        self.assertEqual(c['CSRF_TRUSTED_ORIGINS'], ['https://a.example', 'https://b.example'])

    def test_producao_nao_sobe_sem_as_chaves(self):
        self.assertNotEqual(self.executar(CHAVES_CIFRAGEM='').returncode, 0)
        self.assertNotEqual(self.executar(CHAVE_HASH_CPF='').returncode, 0)

    def test_banco_postgres_usa_ssl_e_serve_para_o_pooler(self):
        db = self.carregar()['db']
        self.assertEqual(db['OPTIONS']['sslmode'], 'require')
        self.assertEqual(db['CONN_MAX_AGE'], 0)
        self.assertTrue(db['DISABLE_SERVER_SIDE_CURSORS'])


class CpfTests(SimpleTestCase):
    def test_aceita_cpf_valido_com_ou_sem_mascara(self):
        self.assertTrue(cpf_valido('529.982.247-25'))
        self.assertTrue(cpf_valido('52998224725'))

    def test_aceita_cpf_com_digito_zero_pela_regra_do_resto(self):
        self.assertTrue(cpf_valido('987.654.321-00'))

    def test_rejeita_invalidos(self):
        for cpf in ('', '123', '12345678901', '11111111111', 'abc'):
            self.assertFalse(cpf_valido(cpf), cpf)


class ArquivosPublicosTests(SimpleTestCase):
    """Varre os arquivos do site, para o problema não voltar em outra página."""

    def arquivos(self, *padroes):
        for padrao in padroes:
            yield from PASTA_CORE.rglob(padrao)

    def test_nenhum_arquivo_aponta_para_servidor_externo_de_dados(self):
        for arquivo in self.arquivos('*.js', '*.html'):
            texto = arquivo.read_text(encoding='utf-8')
            self.assertNotIn('146.235.62.209', texto, arquivo)
            self.assertNotIn('http://', texto.replace('http://www.w3.org', ''), arquivo)

    def test_scripts_nao_escrevem_no_console(self):
        for nome in ('script-cadastro.js', 'script-voluntario-form.js'):
            texto = (PASTA_CORE / 'static' / 'front' / nome).read_text(encoding='utf-8')
            self.assertNotIn('console.', texto, nome)

    def test_nao_usa_google_fonts(self):
        for arquivo in self.arquivos('*.html', '*.css'):
            texto = arquivo.read_text(encoding='utf-8')
            self.assertNotIn('fonts.googleapis.com', texto, arquivo)
            self.assertNotIn('fonts.gstatic.com', texto, arquivo)


@override_settings(STORAGES=STORAGES_TESTE)
class PaginasTests(TestCase):
    def test_aviso_de_privacidade_abre(self):
        r = self.client.get(reverse('privacidade'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ViaCEP')
        self.assertContains(r, 'provisório')

    def test_formularios_tem_aceite_honeypot_e_csrf_e_nao_tem_upload(self):
        for nome in PAGINAS_COM_FORMULARIO:
            r = self.client.get(reverse(nome))
            self.assertContains(r, 'id="aceite_aviso"', msg_prefix=nome)
            self.assertContains(r, 'name="website"', msg_prefix=nome)
            self.assertContains(r, 'csrfmiddlewaretoken', msg_prefix=nome)
            self.assertContains(r, reverse('privacidade'), msg_prefix=nome)
            self.assertNotContains(r, 'type="file"', msg_prefix=nome)

    def test_cadastro_de_assistida_tem_novos_campos(self):
        r = self.client.get(reverse('cadastro_assistida'))
        for campo in ('telefone_assistida', 'pode_deixar_recado', 'melhor_horario', 'numero_assistida'):
            self.assertContains(r, f'id="{campo}"', msg_prefix=campo)

    def test_fontes_estao_no_projeto(self):
        pasta = PASTA_CORE / 'static' / 'front' / 'fonts'
        self.assertTrue(list(pasta.glob('*.woff2')))


class ManterBancoTests(TestCase):
    url = '/manutencao/banco/'

    @override_settings(CRON_SECRET='segredo-de-teste')
    def test_com_o_segredo_consulta_o_banco(self):
        r = self.client.get(self.url, headers={'Authorization': 'Bearer segredo-de-teste'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'ok': True})

    @override_settings(CRON_SECRET='segredo-de-teste')
    def test_segredo_errado_ou_ausente_da_404(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)
        r = self.client.get(self.url, headers={'Authorization': 'Bearer errado'})
        self.assertEqual(r.status_code, 404)

    @override_settings(CRON_SECRET='')
    def test_sem_segredo_configurado_a_rota_fica_desligada(self):
        self.assertEqual(self.client.get(self.url, headers={'Authorization': 'Bearer '}).status_code, 404)

    @override_settings(CRON_SECRET='segredo-de-teste')
    def test_nao_aceita_post(self):
        r = self.client.post(self.url, headers={'Authorization': 'Bearer segredo-de-teste'})
        self.assertEqual(r.status_code, 405)
