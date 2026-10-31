from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import ContaInterna
from core.utils_teste import STORAGES_TESTE

SENHA = 'senha-de-teste-123'
NOVA = 'outra-senha-forte-456'


@override_settings(STORAGES=STORAGES_TESTE, EXIGIR_2FA=False)
class EntrarTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user('ana', password=SENHA)
        ContaInterna.objects.create(usuario=self.usuario, trocar_senha=False)

    def entrar(self, senha=SENHA):
        return self.client.post(reverse('entrar'), {'username': 'ana', 'password': senha})

    def test_login_leva_para_a_area_interna(self):
        self.assertRedirects(self.entrar(), reverse('assistidas_lista'))

    def test_senha_errada_fica_na_tela(self):
        self.assertEqual(self.entrar('errada').status_code, 200)

    def test_bloqueia_depois_de_cinco_erros(self):
        for _ in range(5):
            self.entrar('errada')
        self.assertEqual(self.entrar(SENHA).status_code, 429)

    def test_login_do_admin_vai_para_entrar(self):
        r = self.client.get('/admin/login/?next=/admin/')
        self.assertRedirects(r, '/entrar/?next=/admin/')

    def test_sair_nao_aceita_get(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse('sair')).status_code, 405)

    def test_sair_por_post(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse('sair'))
        self.assertEqual(self.client.get(reverse('assistidas_lista')).status_code, 302)


@override_settings(STORAGES=STORAGES_TESTE, EXIGIR_2FA=False)
class TrocaDeSenhaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user('ana', password=SENHA)
        self.client.force_login(self.usuario)

    def test_conta_nova_e_obrigada_a_trocar(self):
        self.assertRedirects(self.client.get(reverse('assistidas_lista')), reverse('trocar_senha'))

    def test_admin_tambem_exige_a_troca(self):
        self.usuario.is_staff = True
        self.usuario.save()
        self.assertRedirects(self.client.get('/admin/'), reverse('trocar_senha'))

    def test_depois_de_trocar_entra(self):
        r = self.client.post(reverse('trocar_senha'), {
            'old_password': SENHA, 'new_password1': NOVA, 'new_password2': NOVA})
        self.assertRedirects(r, reverse('assistidas_lista'))
        self.assertEqual(self.client.get(reverse('assistidas_lista')).status_code, 200)

    def test_senha_curta_e_recusada(self):
        r = self.client.post(reverse('trocar_senha'), {
            'old_password': SENHA, 'new_password1': 'Ab1x9', 'new_password2': 'Ab1x9'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ContaInterna.objects.filter(usuario=self.usuario, trocar_senha=False).exists())


@override_settings(STORAGES=STORAGES_TESTE, EXIGIR_2FA=True)
class DoisFatoresTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user('ana', password=SENHA)
        ContaInterna.objects.create(usuario=self.usuario, trocar_senha=False)
        self.client.force_login(self.usuario)
        self.lista = reverse('assistidas_lista')

    def codigo(self, dispositivo):
        return f'{totp(dispositivo.bin_key):06d}'

    def test_sem_2fa_nao_entra_na_area_interna(self):
        r = self.client.get(self.lista, follow=True)
        self.assertEqual(r.redirect_chain[-1][0], reverse('configurar_2fa'))

    def test_configura_com_codigo_certo(self):
        self.assertContains(self.client.get(reverse('configurar_2fa')), 'data:image/svg+xml')
        dispositivo = TOTPDevice.objects.get(user=self.usuario)
        self.assertFalse(dispositivo.confirmed)
        r = self.client.post(reverse('configurar_2fa'), {'codigo': self.codigo(dispositivo)})
        self.assertRedirects(r, self.lista)
        dispositivo.refresh_from_db()
        self.assertTrue(dispositivo.confirmed)

    def test_codigo_errado_nao_confirma(self):
        self.client.get(reverse('configurar_2fa'))
        self.client.post(reverse('configurar_2fa'), {'codigo': '000000'})
        self.assertFalse(TOTPDevice.objects.get(user=self.usuario).confirmed)
        self.assertEqual(self.client.get(self.lista).status_code, 302)

    def test_nova_sessao_pede_o_codigo_de_novo(self):
        dispositivo = TOTPDevice.objects.create(user=self.usuario, name='App', confirmed=True)
        self.assertRedirects(self.client.get(self.lista), reverse('verificar_2fa'))
        r = self.client.post(reverse('verificar_2fa'), {'codigo': self.codigo(dispositivo)})
        self.assertRedirects(r, self.lista)
        self.assertEqual(self.client.get(self.lista).status_code, 200)

    def test_reconfigurar_nao_troca_dispositivo_confirmado(self):
        TOTPDevice.objects.create(user=self.usuario, name='App', confirmed=True)
        self.assertRedirects(self.client.get(reverse('configurar_2fa')), self.lista, fetch_redirect_response=False)
        self.assertEqual(TOTPDevice.objects.filter(user=self.usuario).count(), 1)
