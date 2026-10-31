def apenas_digitos(valor):
    return ''.join(filter(str.isdigit, valor))


def formatar_cpf(cpf):
    cpf = apenas_digitos(cpf)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def _digito_cpf(digitos):
    peso_inicial = len(digitos) + 1
    soma = sum(int(d) * (peso_inicial - i) for i, d in enumerate(digitos))
    resto = 11 - (soma % 11)
    return 0 if resto > 9 else resto


def cpf_valido(cpf):
    cpf = apenas_digitos(cpf)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    return (_digito_cpf(cpf[:9]) == int(cpf[9])
            and _digito_cpf(cpf[:10]) == int(cpf[10]))
