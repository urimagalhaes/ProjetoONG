from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('cadastro-assistida/', views.cadastro_assistida, name='cadastro_assistida'),
    # URL antiga mantida para não quebrar links já divulgados
    path('cadastro-vitima/', RedirectView.as_view(pattern_name='cadastro_assistida', permanent=True)),
    path('voluntarios/', views.voluntarios, name='voluntarios'),
    path('voluntarios/advogado/', views.voluntario_advogado, name='voluntario_advogado'),
    path('voluntarios/bacharel/', views.voluntario_bacharel, name='voluntario_bacharel'),
    path('estagio/', views.voluntario_estagiario, name='voluntario_estagiario'),
    path('privacidade/', views.privacidade, name='privacidade'),
    path('noticia/campanha/', views.noticia_campanha, name='noticia_campanha'),
    path('noticia/parceria-universidades/', views.noticia_parceria, name='noticia_parceria'),
    path('noticia/novo-centro/', views.noticia_novo_centro, name='noticia_novo_centro'),
]