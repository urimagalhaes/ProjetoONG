"""
Criptografia dos dados pessoais guardados no banco.

As chaves ficam só em variáveis de ambiente. A primeira de CHAVES_CIFRAGEM cifra;
as demais só decifram, o que permite trocar de chave sem perder dados.
Perder todas as chaves significa perder os dados.
"""
import hashlib
import hmac

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings

from services import apenas_digitos


def _fernet():
    return MultiFernet([Fernet(chave) for chave in settings.CHAVES_CIFRAGEM])


def cifrar(texto):
    return _fernet().encrypt(texto.encode()).decode()


def decifrar(token):
    return _fernet().decrypt(token.encode()).decode()


def hash_cpf(cpf):
    """Permite unicidade e busca exata sem guardar o CPF legível."""
    return hmac.new(
        settings.CHAVE_HASH_CPF.encode(), apenas_digitos(cpf).encode(), hashlib.sha256).hexdigest()
