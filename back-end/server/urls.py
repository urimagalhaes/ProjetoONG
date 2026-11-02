from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # O admin usa a mesma entrada do resto do sistema, com bloqueio de tentativas e 2FA.
    path('admin/login/', RedirectView.as_view(pattern_name='entrar', query_string=True)),
    path('admin/', admin.site.urls),
    path('', include('core.urls_conta')),
    path('', include('core.urls')),
    path('api/voluntarios/', include('voluntarios.urls')),
    path('assistidas/', include('assistidas.urls_paginas')),
    path('painel/', include('painel.urls')),
    path('api/assistidas/', include('assistidas.urls')),
]