"""Ajustes compartilhados pelos testes."""

# O storage de produção (Manifest) exige `collectstatic`; nos testes usamos o simples.
STORAGES_TESTE = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
