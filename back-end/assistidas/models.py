from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.campos import CampoCifrado, CampoJsonCifrado
from core.cripto import hash_cpf

PREFIXO_ANONIMIZADA = 'anonimizada-'


class Assistida(models.Model):
    id_assistida = models.AutoField(primary_key=True)
    cpf_assistida = CampoCifrado(max_length=14)
    cpf_hash = models.CharField(max_length=64, unique=True, editable=False, blank=True)
    nome_assistida = models.CharField(max_length=150)
    cep_assistida = CampoCifrado(max_length=8)
    idade_assistida = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(120)])
    apelido_assistida = models.CharField(max_length=30, blank=True, null=True)
    cidade_assistida = models.CharField(max_length=30)
    estado_assistida = models.CharField(max_length=2)
    rua_assistida = CampoCifrado(max_length=50)
    num_endereco_assistida = CampoCifrado('Número', max_length=10)
    complemento_endereco_assistida = CampoCifrado(max_length=120, blank=True, null=True)
    telefone_assistida = CampoCifrado('Telefone', max_length=11, blank=True, default='')
    # Padrão False: recado pode expor a assistida a quem atender o telefone.
    pode_deixar_recado = models.BooleanField('Pode deixar recado', default=False)
    melhor_horario = CampoCifrado('Melhor horário para contato', max_length=60, blank=True, default='')
    aceite_aviso_em = models.DateTimeField('Aceite do aviso em', blank=True, null=True, editable=False)
    aceite_aviso_versao = models.CharField('Versão do aviso', max_length=10, blank=True, default='', editable=False)

    class Meta:
        db_table = 'Assistidas'
        verbose_name = 'Assistida'
        verbose_name_plural = 'Assistidas'
        ordering = ['nome_assistida']

    def __str__(self):
        return self.nome_assistida

    @property
    def anonimizada(self):
        return self.cpf_hash.startswith(PREFIXO_ANONIMIZADA)

    def save(self, *args, **kwargs):
        if self.cpf_assistida:
            self.cpf_hash = hash_cpf(self.cpf_assistida)
        super().save(*args, **kwargs)


class PendenciaCadastro(models.Model):
    """
    Envio público que não virou cadastro, porque CPF ou OAB já existem.

    Guarda o que foi enviado para a coordenação conferir, sem tocar no cadastro
    existente.
    """
    TIPOS = [
        ('assistida', 'Assistida'),
        ('estagiario', 'Estagiário(a)'),
        ('advogado', 'Advogado(a)'),
        ('bacharel', 'Bacharel'),
    ]

    id_pendencia = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    dados = CampoJsonCifrado()
    criado_em = models.DateTimeField(auto_now_add=True)
    resolvida_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'PendenciasCadastro'
        verbose_name = 'Pendência de cadastro'
        verbose_name_plural = 'Pendências de cadastro'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.get_tipo_display()} em {self.criado_em:%d/%m/%Y %H:%M}"


class VinculoAtendimento(models.Model):
    """
    Liga um voluntário a uma assistida. É a única fonte da regra de acesso ao
    prontuário. Encerrar preenche `fim` e preserva o histórico.
    """
    id_vinculo = models.AutoField(primary_key=True)
    assistida = models.ForeignKey(Assistida, on_delete=models.CASCADE, related_name='vinculos')
    voluntario = models.ForeignKey(
        'voluntarios.Voluntario',
        on_delete=models.PROTECT,
        related_name='vinculos',
        verbose_name='Voluntário',
    )
    designado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Designado por',
    )
    inicio = models.DateTimeField('Início', auto_now_add=True)
    fim = models.DateTimeField('Fim', blank=True, null=True)

    class Meta:
        db_table = 'VinculosAtendimento'
        verbose_name = 'Vínculo de atendimento'
        verbose_name_plural = 'Vínculos de atendimento'
        ordering = ['-inicio']
        constraints = [
            models.UniqueConstraint(
                fields=['assistida', 'voluntario'],
                condition=models.Q(fim__isnull=True),
                name='um_vinculo_ativo_por_par',
            ),
        ]

    def __str__(self):
        return f"{self.voluntario} atende {self.assistida}"


class RegistroProntuario(models.Model):
    """
    Uma entrada do prontuário de uma assistida.

    O prontuário é o conjunto cronológico de registros escritos pelos
    profissionais (voluntários) que atenderam a assistida. Cada registro
    guarda quem escreveu e quando, o que preserva o histórico em vez de
    sobrescrever um único campo de texto.
    """
    id_registro = models.AutoField(primary_key=True)

    id_assistida = models.ForeignKey(
        Assistida,
        on_delete=models.CASCADE,
        db_column='id_assistida',
        related_name='registros_prontuario',
    )

    # PROTECT: não permite apagar um voluntário que já escreveu em prontuários.
    id_autor = models.ForeignKey(
        'voluntarios.Voluntario',
        on_delete=models.PROTECT,
        db_column='id_autor',
        related_name='registros_prontuario',
        verbose_name='Profissional',
    )

    texto = CampoCifrado(verbose_name='Registro')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'RegistrosProntuario'
        verbose_name = 'Registro de prontuário'
        verbose_name_plural = 'Registros de prontuário'
        ordering = ['-criado_em']

    def __str__(self):
        return f"Prontuário de {self.id_assistida.nome_assistida} em {self.criado_em:%d/%m/%Y}"


class RegistroProntuarioVersao(models.Model):
    """Texto anterior de um registro, gravado a cada edição."""
    id_versao = models.AutoField(primary_key=True)
    registro = models.ForeignKey(RegistroProntuario, on_delete=models.CASCADE, related_name='versoes')
    texto_anterior = CampoCifrado()
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    editado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'RegistrosProntuarioVersoes'
        verbose_name = 'Versão de registro de prontuário'
        verbose_name_plural = 'Versões de registros de prontuário'
        ordering = ['-editado_em']


class SomenteInclusaoQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError('O registro de acessos não pode ser alterado.')

    def delete(self):
        raise TypeError('O registro de acessos não pode ser apagado.')


class RegistroAcesso(models.Model):
    """
    Trilha de auditoria: quem fez o quê com qual assistida.

    Guarda ids soltos e cópia do login para sobreviver à exclusão da assistida
    ou do usuário. Nunca guarda o conteúdo acessado.
    """
    ACOES = [
        ('leitura', 'Leitura de prontuário'),
        ('criacao', 'Criação de registro'),
        ('edicao', 'Edição de registro'),
        ('exportacao', 'Exportação de dados'),
        ('anonimizacao', 'Anonimização de assistida'),
        ('exclusao', 'Exclusão de assistida'),
        ('negacao', 'Acesso negado'),
        ('vinculo_criado', 'Vínculo criado'),
        ('vinculo_encerrado', 'Vínculo encerrado'),
        ('usuario_vinculado', 'Login ligado a voluntário'),
        ('senha_redefinida', 'Senha redefinida por terceiro'),
        ('acesso_alterado', 'Acesso de usuário alterado'),
        ('cadastro_alterado', 'Cadastro de assistida alterado'),
    ]

    id_acesso = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    login = models.CharField(max_length=150)
    acao = models.CharField(max_length=20, choices=ACOES)
    id_assistida = models.IntegerField(blank=True, null=True)
    id_registro = models.IntegerField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(blank=True, null=True)

    objects = SomenteInclusaoQuerySet.as_manager()

    class Meta:
        db_table = 'RegistrosAcesso'
        verbose_name = 'Registro de acesso'
        verbose_name_plural = 'Registros de acesso'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.login}: {self.get_acao_display()}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise TypeError('O registro de acessos não pode ser alterado.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError('O registro de acessos não pode ser apagado.')
