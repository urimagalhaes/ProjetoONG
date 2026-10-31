from django import forms
from django.contrib import admin

from assistidas.auditoria import registrar
from core.cadastro import validar_cpf_do_formulario
from .models import Voluntario, Estagiario, Advogado, Bacharel, DisponibilidadeEstagiario


class VoluntarioAdminForm(forms.ModelForm):
    class Meta:
        model = Voluntario
        fields = '__all__'

    def clean_cpf_voluntario(self):
        return validar_cpf_do_formulario(self, 'cpf_voluntario', 'cpf_hash_voluntario')


class DisponibilidadeInline(admin.TabularInline):
    model = DisponibilidadeEstagiario
    extra = 1
    fields = ['diasemana_estagiario', 'iniciodisponibilidade_estagiario', 'fimdisponibilidade_estagiario']

@admin.register(Voluntario)
class VoluntarioAdmin(admin.ModelAdmin):
    form = VoluntarioAdminForm

    list_display = [
        'id_voluntario', 
        'nomecompleto_voluntario', 
        'email_voluntario', 
        'telefone_voluntario',
        'cidade_voluntario',
        'tipo_voluntario',
    ]
    
    list_filter = ['sexo_voluntario', 'estado_voluntario', 'cidade_voluntario']
    
    search_fields = [
        'nomecompleto_voluntario', 
        'email_voluntario',
    ]
    
    list_per_page = 25
    
    fieldsets = (
        ('Informações Pessoais', {
            'fields': (
                'nomecompleto_voluntario',
                'email_voluntario',
                'datanasc_voluntario',
                'sexo_voluntario'
            )
        }),
        ('Documentos', {
            'fields': ('cpf_voluntario', 'rg_voluntario')
        }),
        ('Localização', {
            'fields': ('endereco_voluntario', 'cidade_voluntario', 'estado_voluntario')
        }),
        ('Contato', {
            'fields': ('telefone_voluntario', 'instagram_voluntario')
        }),
        ('Uploads', {
            'fields': ('cpfupload_voluntario', 'fotoupload_voluntario', 'termoupload_voluntario')
        }),
        ('Acesso ao sistema', {
            'fields': ('usuario',)
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'usuario' and not request.user.is_superuser:
            kwargs['queryset'] = db_field.remote_field.model.objects.filter(is_superuser=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if 'usuario' in form.changed_data:
            registrar(request, 'usuario_vinculado')

    @admin.display(description='Tipo')
    def tipo_voluntario(self, obj):
        return obj.tipo
    
@admin.register(Estagiario)
class EstagiarioAdmin(admin.ModelAdmin):
    list_display = [
        'id_estagiario',
        'get_nome_voluntario',
        'curso_estagiario',
        'periodo_estagiario'
    ]
    
    search_fields = ['id_voluntario__nomecompleto_voluntario', 'curso_estagiario']
    list_filter = ['curso_estagiario', 'periodo_estagiario']
    readonly_fields = ['id_estagiario']
    inlines = [DisponibilidadeInline]
    
    @admin.display(description='Nome', ordering='id_voluntario__nomecompleto_voluntario')
    def get_nome_voluntario(self, obj):
        return obj.id_voluntario.nomecompleto_voluntario

@admin.register(Advogado)
class AdvogadoAdmin(admin.ModelAdmin):
    list_display = [
        'id_advogado',
        'get_nome_voluntario',
        'oab_advogado'
    ]
    
    search_fields = ['id_voluntario__nomecompleto_voluntario', 'oab_advogado']
    readonly_fields = ['id_advogado']
    
    @admin.display(description='Nome', ordering='id_voluntario__nomecompleto_voluntario')
    def get_nome_voluntario(self, obj):
        return obj.id_voluntario.nomecompleto_voluntario
    
@admin.register(Bacharel)
class BacharelAdmin(admin.ModelAdmin):
    list_display = [
        'id_bacharel',
        'get_nome_voluntario',
        'cursoformacao_bacharel'
    ]
    
    search_fields = ['id_voluntario__nomecompleto_voluntario', 'cursoformacao_bacharel']
    list_filter = ['cursoformacao_bacharel']
    readonly_fields = ['id_bacharel']
    
    @admin.display(description='Nome', ordering='id_voluntario__nomecompleto_voluntario')
    def get_nome_voluntario(self, obj):
        return obj.id_voluntario.nomecompleto_voluntario

@admin.register(DisponibilidadeEstagiario)
class DisponibilidadeEstagiarioAdmin(admin.ModelAdmin):
    list_display = [
        'id_disponibilidadeestagiario',
        'get_nome_estagiario',
        'diasemana_estagiario',
        'iniciodisponibilidade_estagiario',
        'fimdisponibilidade_estagiario'
    ]
    
    list_filter = ['diasemana_estagiario']
    search_fields = ['id_estagiario__id_voluntario__nomecompleto_voluntario']
    
    @admin.display(description='Estagiário', ordering='id_estagiario__id_voluntario__nomecompleto_voluntario')
    def get_nome_estagiario(self, obj):
        return obj.id_estagiario.id_voluntario.nomecompleto_voluntario