from django.conf import settings
from django.db import models


class ContaInterna(models.Model):
    """Estado de acesso da conta. Sem esta linha, a troca de senha é exigida."""
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conta_interna')
    trocar_senha = models.BooleanField('Precisa trocar a senha', default=True)

    class Meta:
        db_table = 'ContasInternas'
        verbose_name = 'Conta interna'
        verbose_name_plural = 'Contas internas'

    def __str__(self):
        return str(self.usuario)
