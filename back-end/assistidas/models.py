from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Assistida(models.Model):
    id_assistida = models.AutoField(primary_key=True)
    cpf_assistida = models.CharField(max_length=14, unique=True)
    nome_assistida = models.CharField(max_length=150)
    cep_assistida = models.CharField(max_length=8)
    idade_assistida = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(120)])
    apelido_assistida = models.CharField(max_length=30, blank=True, null=True)
    cidade_assistida = models.CharField(max_length=30)
    estado_assistida = models.CharField(max_length=2)
    rua_assistida = models.CharField(max_length=50)
    num_endereco_assistida = models.CharField('Número', max_length=10)
    complemento_endereco_assistida = models.CharField(max_length=120, blank=True, null=True)
    telefone_assistida = models.CharField('Telefone', max_length=11, blank=True, default='')
    # Padrão False: recado pode expor a assistida a quem atender o telefone.
    pode_deixar_recado = models.BooleanField('Pode deixar recado', default=False)
    melhor_horario = models.CharField('Melhor horário para contato', max_length=60, blank=True, default='')
    aceite_aviso_em = models.DateTimeField('Aceite do aviso em', blank=True, null=True, editable=False)
    aceite_aviso_versao = models.CharField('Versão do aviso', max_length=10, blank=True, default='', editable=False)

    class Meta:
        db_table = 'Assistidas'
        verbose_name = 'Assistida'
        verbose_name_plural = 'Assistidas'
        ordering = ['nome_assistida']

    def __str__(self):
        return self.nome_assistida


class PendenciaCadastro(models.Model):
    """
    Envio público que não virou cadastro, porque CPF ou OAB já existem.

    Guarda o que foi enviado para a coordenação conferir, sem tocar no cadastro
    existente. `dados` contém dados pessoais e será cifrado na Fase 4.
    """
    TIPOS = [
        ('assistida', 'Assistida'),
        ('estagiario', 'Estagiário(a)'),
        ('advogado', 'Advogado(a)'),
        ('bacharel', 'Bacharel'),
    ]

    id_pendencia = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    dados = models.JSONField()
    criado_em = models.DateTimeField(auto_now_add=True)
    resolvida_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'PendenciasCadastro'
        verbose_name = 'Pendência de cadastro'
        verbose_name_plural = 'Pendências de cadastro'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.get_tipo_display()} em {self.criado_em:%d/%m/%Y %H:%M}"


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

    texto = models.TextField(verbose_name='Registro')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'RegistrosProntuario'
        verbose_name = 'Registro de prontuário'
        verbose_name_plural = 'Registros de prontuário'
        ordering = ['-criado_em']

    def __str__(self):
        return f"Prontuário de {self.id_assistida.nome_assistida} em {self.criado_em:%d/%m/%Y}"
