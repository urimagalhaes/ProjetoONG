from django.urls import path
from . import views

# Montado em /assistidas/  (acesso só com vínculo; ver permissoes.py)
urlpatterns = [
    path('', views.lista, name='assistidas_lista'),
    path('<int:id_assistida>/prontuario/', views.prontuario, name='assistida_prontuario'),
    path('<int:id_assistida>/prontuario/novo/', views.novo_registro, name='registro_novo'),
    path('<int:id_assistida>/prontuario/<int:id_registro>/editar/', views.editar_registro, name='registro_editar'),
]
