from django.db import models

class Voluntario(models.Model):
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('O', 'Outro'),
    ]
    
    id_voluntario = models.AutoField(primary_key=True)
    email_voluntario = models.EmailField(max_length=100)
    nomecompleto_voluntario = models.CharField(max_length=150)
    datanasc_voluntario = models.DateField()
    sexo_voluntario = models.CharField(max_length=1, choices=SEXO_CHOICES)
    cidade_voluntario = models.CharField(max_length=30)
    estado_voluntario = models.CharField(max_length=2)
    endereco_voluntario = models.CharField(max_length=50)
    telefone_voluntario = models.CharField(max_length=9)
    instagram_voluntario = models.CharField(max_length=30, blank=True, default='')
    cpf_voluntario = models.CharField(max_length=14, unique=True)  
    rg_voluntario = models.CharField(max_length=9)
    # Marcados pela equipe quando recebe o documento. O site não recebe arquivos.
    cpfupload_voluntario = models.BooleanField(default=False)
    fotoupload_voluntario = models.BooleanField(default=False)
    termoupload_voluntario = models.BooleanField(default=False)
    aceite_aviso_em = models.DateTimeField('Aceite do aviso em', blank=True, null=True, editable=False)
    aceite_aviso_versao = models.CharField('Versão do aviso', max_length=10, blank=True, default='', editable=False)

    class Meta:
        db_table = 'Voluntarios'
    
    def __str__(self):
        return self.nomecompleto_voluntario

    @property
    def tipo(self):
        if hasattr(self, 'estagiario'):
            return 'Estagiário(a)'
        if hasattr(self, 'advogado'):
            return 'Advogado(a)'
        if hasattr(self, 'bacharel'):
            return 'Bacharel'
        return 'Voluntário(a)'

class Estagiario(models.Model):
    PERIODOS = [
        ('1', '1º Período'),
        ('2', '2º Período'),
        ('3', '3º Período'),
        ('4', '4º Período'),
        ('5', '5º Período'),
        ('6', '6º Período'),
        ('7', '7º Período'),
        ('8', '8º Período'),
        ('9', '9º Período'),
        ('10', '10º Período'),
    ]
    
    id_estagiario = models.AutoField(primary_key=True)
    
    id_voluntario = models.OneToOneField(
        Voluntario,
        on_delete=models.CASCADE,
        db_column='id_voluntario',
        related_name='estagiario'
    )
    
    curso_estagiario = models.CharField(max_length=20)
    periodo_estagiario = models.CharField(max_length=2, choices=PERIODOS)
    
    class Meta:
        db_table = 'Estagiarios'
        verbose_name = 'Estagiário'
        verbose_name_plural = 'Estagiários'
    
    def __str__(self):
        return f"{self.id_voluntario.nomecompleto_voluntario} - Estagiário"

class Advogado(models.Model):
    id_advogado = models.AutoField(primary_key=True)
    
    id_voluntario = models.OneToOneField(
        Voluntario,
        on_delete=models.CASCADE,
        db_column='id_voluntario',
        related_name='advogado'
    )
    
    oab_advogado = models.CharField(max_length=9, unique=True)
    
    class Meta:
        db_table = 'Advogados'
        verbose_name = 'Advogado'
        verbose_name_plural = 'Advogados'
    
    def __str__(self):
        return f"{self.id_voluntario.nomecompleto_voluntario} - OAB: {self.oab_advogado}"
    
class Bacharel(models.Model):
    id_bacharel = models.AutoField(primary_key=True)
    
    id_voluntario = models.OneToOneField(
        Voluntario,
        on_delete=models.CASCADE,
        db_column='id_voluntario',
        related_name='bacharel'
    )
    
    cursoformacao_bacharel = models.CharField(max_length=20)
    
    class Meta:
        db_table = 'Bachareis'
        verbose_name = 'Bacharel'
        verbose_name_plural = 'Bacharéis'
    
    def __str__(self):
        return f"{self.id_voluntario.nomecompleto_voluntario} - Bacharel em {self.cursoformacao_bacharel}"

class DisponibilidadeEstagiario(models.Model):
    DIAS_SEMANA = [
        ('SEG', 'Segunda-feira'),
        ('TER', 'Terça-feira'),
        ('QUA', 'Quarta-feira'),
        ('QUI', 'Quinta-feira'),
        ('SEX', 'Sexta-feira'),
        ('SAB', 'Sábado'),
        ('DOM', 'Domingo'),
    ]
    
    id_disponibilidadeestagiario = models.AutoField(primary_key=True)
    
    id_estagiario = models.ForeignKey(
        Estagiario,
        on_delete=models.CASCADE,
        db_column='id_estagiario',
        related_name='disponibilidades'
    )
    
    diasemana_estagiario = models.CharField(max_length=20, choices=DIAS_SEMANA)
    iniciodisponibilidade_estagiario = models.TimeField()
    fimdisponibilidade_estagiario = models.TimeField()
    
    class Meta:
        db_table = 'DisponibilidadesEstagiarios'
        verbose_name = 'Disponibilidade do Estagiário'
        verbose_name_plural = 'Disponibilidades dos Estagiários'
    
    def __str__(self):
        return f"{self.id_estagiario.id_voluntario.nomecompleto_voluntario} - {self.diasemana_estagiario}"