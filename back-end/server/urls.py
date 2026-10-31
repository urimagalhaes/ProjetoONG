from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('api/voluntarios/', include('voluntarios.urls')),
    path('assistidas/', include('assistidas.urls_paginas')),
    path('api/assistidas/', include('assistidas.urls')),
]