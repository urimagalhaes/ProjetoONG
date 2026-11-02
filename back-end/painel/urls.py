from django.urls import path

from . import views

# Montado em /painel/ (só Coordenação). Prontuário não passa por aqui.
urlpatterns = [
    path('', views.inicio, name='painel_inicio'),
    path('assistidas/', views.assistidas, name='painel_assistidas'),
    path('assistidas/nova/', views.assistida_nova, name='painel_assistida_nova'),
    path('assistidas/<int:id_assistida>/', views.assistida, name='painel_assistida'),
    path('assistidas/<int:id_assistida>/editar/', views.assistida_editar, name='painel_assistida_editar'),
    path('assistidas/<int:id_assistida>/atendentes/', views.atendente_adicionar, name='painel_atendente_adicionar'),
    path('assistidas/<int:id_assistida>/atendentes/<int:id_vinculo>/encerrar/', views.atendente_encerrar,
         name='painel_atendente_encerrar'),
    path('assistidas/<int:id_assistida>/<str:acao>/', views.assistida_direito, name='painel_assistida_direito'),
    path('equipe/', views.equipe, name='painel_equipe'),
    path('equipe/adicionar/', views.pessoa_adicionar, name='painel_pessoa_adicionar'),
    path('equipe/eu-atendo/', views.eu_atendo, name='painel_eu_atendo'),
    path('equipe/<int:id_voluntario>/', views.pessoa, name='painel_pessoa'),
    path('equipe/<int:id_voluntario>/acesso/<str:acao>/', views.pessoa_acesso, name='painel_pessoa_acesso'),
    path('pendencias/', views.pendencias, name='painel_pendencias'),
    path('pendencias/<int:id_pendencia>/resolver/', views.pendencia_resolver, name='painel_pendencia_resolver'),
    path('atendimentos/', views.atendimentos, name='painel_atendimentos'),
    path('atendimentos/<int:id_atendimento>/cancelar/', views.atendimento_cancelar, name='painel_atendimento_cancelar'),
    path('acessos/', views.acessos, name='painel_acessos'),
]
