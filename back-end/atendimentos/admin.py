from django.contrib import admin
from .models import Atendimento


@admin.register(Atendimento)
class AtendimentoAdmin(admin.ModelAdmin):
    list_display = (
        'id_atendimento',
        'get_nome_assistida',
        'get_nome_estagiario',
        'data_atendimento',
        'hora_atendimento'
    )
    
    list_filter = (
        'data_atendimento',
        'id_estagiario'
    )
    
    search_fields = (
        'id_assistida__nome_assistida',
        'id_estagiario__id_voluntario__nomecompleto_voluntario'
    )
    
    date_hierarchy = 'data_atendimento'
    
    fieldsets = (
        ('Informações da Assistida', {
            'fields': ('id_assistida',)
        }),
        ('Estagiário Responsável', {
            'fields': ('id_estagiario',)
        }),
        ('Data e Hora', {
            'fields': ('data_atendimento', 'hora_atendimento')
        }),
    )
    
    # Métodos personalizados para exibição
    def get_nome_assistida(self, obj):
        return obj.id_assistida.nome_assistida
    get_nome_assistida.short_description = 'Assistida'
    get_nome_assistida.admin_order_field = 'id_assistida__nome_assistida'
    
    def get_nome_estagiario(self, obj):
        if obj.id_estagiario is None:
            return '—'
        return obj.id_estagiario.id_voluntario.nomecompleto_voluntario
    get_nome_estagiario.short_description = 'Estagiário'
    get_nome_estagiario.admin_order_field = 'id_estagiario__id_voluntario__nomecompleto_voluntario'
    
    # Configurações adicionais
    save_on_top = True
    list_per_page = 25