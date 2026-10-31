from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views_conta

urlpatterns = [
    path('entrar/', views_conta.Entrar.as_view(), name='entrar'),
    path('sair/', LogoutView.as_view(), name='sair'),
    path('trocar-senha/', views_conta.TrocarSenha.as_view(), name='trocar_senha'),
    path('2fa/', views_conta.verificar_2fa, name='verificar_2fa'),
    path('2fa/configurar/', views_conta.configurar_2fa, name='configurar_2fa'),
]
