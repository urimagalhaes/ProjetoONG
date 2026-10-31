from django.urls import path
from . import views

# Montado em /assistidas/  (acesso só com vínculo; ver permissoes.py)
urlpatterns = [
    path('', views.lista, name='assistidas_lista'),
    path('<int:id_assistida>/prontuario/', views.prontuario, name='assistida_prontuario'),
]
