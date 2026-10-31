from django.db import migrations, models

import core.campos
from core.cripto import cifrar, decifrar, hash_cpf

CAMPOS = ('cpf_voluntario', 'rg_voluntario', 'telefone_voluntario', 'endereco_voluntario')


def _converter(modelo, funcao):
    for linha in modelo.objects.all():
        valores = {}
        for campo in CAMPOS:
            valor = getattr(linha, campo)
            valores[campo] = funcao(valor) if valor else valor
        modelo.objects.filter(pk=linha.pk).update(**valores)


def cifrar_linhas(apps, schema_editor):
    Voluntario = apps.get_model('voluntarios', 'Voluntario')
    for voluntario in Voluntario.objects.all():
        Voluntario.objects.filter(pk=voluntario.pk).update(
            cpf_hash_voluntario=hash_cpf(voluntario.cpf_voluntario))
    _converter(Voluntario, cifrar)


def decifrar_linhas(apps, schema_editor):
    _converter(apps.get_model('voluntarios', 'Voluntario'), decifrar)


class Migration(migrations.Migration):
    """Mesma sequência de assistidas.0005: texto, cifra as linhas, campo cifrado."""

    dependencies = [
        ('voluntarios', '0010_voluntario_usuario'),
    ]

    operations = [
        migrations.AddField(
            model_name='voluntario',
            name='cpf_hash_voluntario',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True),
        ),
        migrations.AlterField(model_name='voluntario', name='cpf_voluntario', field=models.TextField()),
        migrations.AlterField(model_name='voluntario', name='rg_voluntario', field=models.TextField()),
        migrations.AlterField(model_name='voluntario', name='telefone_voluntario', field=models.TextField()),
        migrations.AlterField(model_name='voluntario', name='endereco_voluntario', field=models.TextField()),
        migrations.RunPython(cifrar_linhas, decifrar_linhas),
        migrations.AlterField(
            model_name='voluntario', name='cpf_voluntario', field=core.campos.CampoCifrado(max_length=14)),
        migrations.AlterField(
            model_name='voluntario', name='rg_voluntario', field=core.campos.CampoCifrado(max_length=9)),
        migrations.AlterField(
            model_name='voluntario', name='telefone_voluntario', field=core.campos.CampoCifrado(max_length=9)),
        migrations.AlterField(
            model_name='voluntario', name='endereco_voluntario', field=core.campos.CampoCifrado(max_length=50)),
        migrations.AlterField(
            model_name='voluntario', name='cpf_hash_voluntario',
            field=models.CharField(blank=True, editable=False, max_length=64, unique=True),
        ),
    ]
