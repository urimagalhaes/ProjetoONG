import json

from django import forms
from django.core import validators
from django.db import models

from .cripto import cifrar, decifrar


class CampoCifrado(models.TextField):
    """
    Texto cifrado no banco e legível no Python.

    O conteúdo cifrado muda a cada gravação, então o banco não consegue buscar
    por ele. Filtros levantam FieldError em vez de voltar vazio sem aviso.
    Só `isnull` funciona. Para buscar, use um campo de hash.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.max_length is not None:
            self.validators.append(validators.MaxLengthValidator(self.max_length))

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return cifrar(value) if value else value

    def from_db_value(self, value, expression, connection):
        return decifrar(value) if value else value

    def get_lookup(self, lookup_name):
        return super().get_lookup(lookup_name) if lookup_name == 'isnull' else None

    def formfield(self, **kwargs):
        if self.max_length is not None:
            kwargs['widget'] = forms.TextInput
        return super().formfield(**kwargs)


class CampoJsonCifrado(CampoCifrado):
    def get_prep_value(self, value):
        return value if value is None else super().get_prep_value(json.dumps(value))

    def from_db_value(self, value, expression, connection):
        texto = super().from_db_value(value, expression, connection)
        return json.loads(texto) if texto else texto

    def to_python(self, value):
        return value
