import base64
import io

import segno
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import ContaInterna


class FormCodigo(forms.Form):
    codigo = forms.CharField(
        label='Código de 6 dígitos', max_length=6, min_length=6,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}))


@method_decorator(never_cache, name='dispatch')
class Entrar(LoginView):
    template_name = 'conta/entrar.html'
    redirect_authenticated_user = True


@method_decorator(never_cache, name='dispatch')
class TrocarSenha(PasswordChangeView):
    template_name = 'conta/trocar_senha.html'
    success_url = reverse_lazy('assistidas_lista')

    def form_valid(self, form):
        resposta = super().form_valid(form)
        ContaInterna.objects.update_or_create(
            usuario=self.request.user, defaults={'trocar_senha': False})
        return resposta


def _dispositivo_confirmado(usuario):
    return TOTPDevice.objects.filter(user=usuario, confirmed=True).first()


def _qr_em_data_uri(url):
    saida = io.BytesIO()
    segno.make(url, error='m').save(saida, kind='svg', scale=5)
    return 'data:image/svg+xml;base64,' + base64.b64encode(saida.getvalue()).decode()


@never_cache
@login_required
def configurar_2fa(request):
    if not settings.EXIGIR_2FA or _dispositivo_confirmado(request.user):
        return redirect('assistidas_lista')

    # Um dispositivo pendente por pessoa: recarregar a página não troca o QR.
    dispositivo, _ = TOTPDevice.objects.get_or_create(
        user=request.user, confirmed=False, defaults={'name': 'Aplicativo'})
    form = FormCodigo(request.POST or None)
    if form.is_valid():
        if dispositivo.verify_token(form.cleaned_data['codigo']):
            dispositivo.confirmed = True
            dispositivo.save()
            otp_login(request, dispositivo)
            return redirect('assistidas_lista')
        form.add_error('codigo', 'Código incorreto. Confira o horário do celular e tente de novo.')
    return render(request, 'conta/configurar_2fa.html', {
        'form': form,
        'qr': _qr_em_data_uri(dispositivo.config_url),
        'chave': base64.b32encode(dispositivo.bin_key).decode(),
    })


@never_cache
@login_required
def verificar_2fa(request):
    dispositivo = _dispositivo_confirmado(request.user)
    if dispositivo is None:
        return redirect('configurar_2fa')
    if request.user.is_verified():
        return redirect('assistidas_lista')

    form = FormCodigo(request.POST or None)
    if form.is_valid():
        if dispositivo.verify_token(form.cleaned_data['codigo']):
            otp_login(request, dispositivo)
            return redirect('assistidas_lista')
        form.add_error('codigo', 'Código incorreto.')
    return render(request, 'conta/verificar_2fa.html', {'form': form})
