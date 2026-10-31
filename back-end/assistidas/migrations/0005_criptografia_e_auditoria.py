import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import assistidas.models
import core.campos
from core.cripto import cifrar, decifrar, hash_cpf

CAMPOS_ASSISTIDA = (
    'cpf_assistida', 'cep_assistida', 'rua_assistida', 'num_endereco_assistida',
    'complemento_endereco_assistida', 'telefone_assistida', 'melhor_horario',
)


def _converter(modelo, campos, funcao):
    for linha in modelo.objects.all():
        valores = {}
        for campo in campos:
            valor = getattr(linha, campo)
            valores[campo] = funcao(valor) if valor else valor
        modelo.objects.filter(pk=linha.pk).update(**valores)


def cifrar_linhas(apps, schema_editor):
    Assistida = apps.get_model('assistidas', 'Assistida')
    for assistida in Assistida.objects.all():
        Assistida.objects.filter(pk=assistida.pk).update(cpf_hash=hash_cpf(assistida.cpf_assistida))
    _converter(Assistida, CAMPOS_ASSISTIDA, cifrar)
    _converter(apps.get_model('assistidas', 'RegistroProntuario'), ['texto'], cifrar)
    _converter(apps.get_model('assistidas', 'PendenciaCadastro'), ['dados'], cifrar)


def decifrar_linhas(apps, schema_editor):
    _converter(apps.get_model('assistidas', 'Assistida'), CAMPOS_ASSISTIDA, decifrar)
    _converter(apps.get_model('assistidas', 'RegistroProntuario'), ['texto'], decifrar)
    _converter(apps.get_model('assistidas', 'PendenciaCadastro'), ['dados'], decifrar)


class Migration(migrations.Migration):
    """
    Passa os campos para texto, cifra as linhas existentes e só então troca para
    os campos cifrados. A reversão decifra as linhas no caminho de volta.
    """

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('assistidas', '0004_vinculoatendimento'),
    ]

    operations = [
        migrations.AddField(
            model_name='assistida',
            name='cpf_hash',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True),
        ),
        migrations.AlterField(model_name='assistida', name='cpf_assistida', field=models.TextField()),
        migrations.AlterField(model_name='assistida', name='cep_assistida', field=models.TextField()),
        migrations.AlterField(model_name='assistida', name='rua_assistida', field=models.TextField()),
        migrations.AlterField(model_name='assistida', name='num_endereco_assistida', field=models.TextField()),
        migrations.AlterField(
            model_name='assistida', name='complemento_endereco_assistida',
            field=models.TextField(blank=True, null=True)),
        migrations.AlterField(
            model_name='assistida', name='telefone_assistida', field=models.TextField(blank=True, default='')),
        migrations.AlterField(
            model_name='assistida', name='melhor_horario', field=models.TextField(blank=True, default='')),
        migrations.AlterField(model_name='pendenciacadastro', name='dados', field=models.TextField()),
        migrations.RunPython(cifrar_linhas, decifrar_linhas),
        migrations.AlterField(
            model_name='assistida', name='cpf_assistida', field=core.campos.CampoCifrado(max_length=14)),
        migrations.AlterField(
            model_name='assistida', name='cep_assistida', field=core.campos.CampoCifrado(max_length=8)),
        migrations.AlterField(
            model_name='assistida', name='rua_assistida', field=core.campos.CampoCifrado(max_length=50)),
        migrations.AlterField(
            model_name='assistida', name='num_endereco_assistida',
            field=core.campos.CampoCifrado(max_length=10, verbose_name='Número')),
        migrations.AlterField(
            model_name='assistida', name='complemento_endereco_assistida',
            field=core.campos.CampoCifrado(blank=True, max_length=120, null=True)),
        migrations.AlterField(
            model_name='assistida', name='telefone_assistida',
            field=core.campos.CampoCifrado(blank=True, default='', max_length=11, verbose_name='Telefone')),
        migrations.AlterField(
            model_name='assistida', name='melhor_horario',
            field=core.campos.CampoCifrado(
                blank=True, default='', max_length=60, verbose_name='Melhor horário para contato')),
        migrations.AlterField(
            model_name='assistida', name='cpf_hash',
            field=models.CharField(blank=True, editable=False, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='pendenciacadastro', name='dados', field=core.campos.CampoJsonCifrado()),
        migrations.AlterField(
            model_name='registroprontuario', name='texto',
            field=core.campos.CampoCifrado(verbose_name='Registro')),
        migrations.CreateModel(
            name='RegistroAcesso',
            fields=[
                ('id_acesso', models.AutoField(primary_key=True, serialize=False)),
                ('login', models.CharField(max_length=150)),
                ('acao', models.CharField(choices=assistidas.models.RegistroAcesso.ACOES, max_length=20)),
                ('id_assistida', models.IntegerField(blank=True, null=True)),
                ('id_registro', models.IntegerField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('usuario', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Registro de acesso',
                'verbose_name_plural': 'Registros de acesso',
                'db_table': 'RegistrosAcesso',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='RegistroProntuarioVersao',
            fields=[
                ('id_versao', models.AutoField(primary_key=True, serialize=False)),
                ('texto_anterior', core.campos.CampoCifrado()),
                ('editado_em', models.DateTimeField(auto_now_add=True)),
                ('editado_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
                ('registro', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='versoes',
                    to='assistidas.registroprontuario')),
            ],
            options={
                'verbose_name': 'Versão de registro de prontuário',
                'verbose_name_plural': 'Versões de registros de prontuário',
                'db_table': 'RegistrosProntuarioVersoes',
                'ordering': ['-editado_em'],
            },
        ),
    ]
