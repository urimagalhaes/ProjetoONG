from django.db import models

class Atendimento(models.Model):
    id_atendimento = models.AutoField(primary_key=True)
    
    id_assistida = models.ForeignKey(
        'assistidas.Assistida',
        on_delete=models.CASCADE,
        db_column='id_assistida',
        related_name='atendimentos'
    )
    
    id_estagiario = models.ForeignKey(
        'voluntarios.Estagiario',
        on_delete=models.CASCADE,
        db_column='id_estagiario',
        related_name='atendimentos',
        null=True,
        blank=True
    )
    
    # Campos do atendimento
    data_atendimento = models.DateField()
    hora_atendimento = models.TimeField()
    
    class Meta:
        db_table = 'Atendimentos'
        verbose_name = 'Atendimento'
        verbose_name_plural = 'Atendimentos'
        ordering = ['-data_atendimento']
        unique_together = ('id_estagiario', 'data_atendimento', 'hora_atendimento')
    
    def __str__(self):
        return f"Atendimento #{self.id_atendimento} - {self.id_assistida.nome_assistida}"