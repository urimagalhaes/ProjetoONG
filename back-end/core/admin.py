from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from assistidas.auditoria import registrar
from assistidas.permissoes import GRUPO_ATENDIMENTO, GRUPO_COORDENACAO
from .models import ContaInterna

Usuario = get_user_model()
admin.site.unregister(Usuario)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """
    A Coordenação cria logins e redefine senhas, mas não enxerga superusuários
    nem distribui permissões avulsas. Quem entra no admin decorre do grupo.
    """

    def get_queryset(self, request):
        usuarios = super().get_queryset(request)
        return usuarios if request.user.is_superuser else usuarios.filter(is_superuser=False)

    def get_fieldsets(self, request, obj=None):
        if obj is None or request.user.is_superuser:
            return super().get_fieldsets(request, obj)
        return (
            (None, {'fields': ('username', 'password')}),
            ('Dados pessoais', {'fields': ('first_name', 'last_name', 'email')}),
            ('Acesso', {'fields': ('is_active', 'groups')}),
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'groups' and not request.user.is_superuser:
            kwargs['queryset'] = Group.objects.filter(name__in=[GRUPO_COORDENACAO, GRUPO_ATENDIMENTO])
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if not request.user.is_superuser:
            usuario = form.instance
            usuario.is_staff = usuario.groups.filter(name=GRUPO_COORDENACAO).exists()
            usuario.save(update_fields=['is_staff'])

    def user_change_password(self, request, id, form_url=''):
        resposta = super().user_change_password(request, id, form_url)
        if request.method == 'POST' and resposta.status_code == 302:
            ContaInterna.objects.update_or_create(usuario_id=id, defaults={'trocar_senha': True})
            registrar(request, 'senha_redefinida')
        return resposta
