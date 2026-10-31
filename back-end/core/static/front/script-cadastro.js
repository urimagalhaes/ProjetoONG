document.addEventListener('DOMContentLoaded', function () {
    // Máscaras para CPF e CEP
    const cpfInput = document.getElementById('cpf_assistida');
    const cepInput = document.getElementById('cep_assistida');
    const telefoneInput = document.getElementById('telefone_assistida');

    // Máscara CPF
    cpfInput.addEventListener('input', function (e) {
        let value = e.target.value.replace(/\D/g, '');
        value = value.replace(/(\d{3})(\d)/, '$1.$2');
        value = value.replace(/(\d{3})(\d)/, '$1.$2');
        value = value.replace(/(\d{3})(\d{1,2})$/, '$1-$2');
        e.target.value = value;
    });

    // Máscara CEP
    cepInput.addEventListener('input', function (e) {
        let value = e.target.value.replace(/\D/g, '');
        value = value.replace(/(\d{5})(\d)/, '$1-$2');
        e.target.value = value;
    });

    // Máscara telefone
    telefoneInput.addEventListener('input', function (e) {
        let value = e.target.value.replace(/\D/g, '').slice(0, 11);
        value = value.replace(/^(\d{2})(\d)/, '($1) $2');
        value = value.replace(/(\d{4,5})(\d{4})$/, '$1-$2');
        e.target.value = value;
    });

    // Buscar endereço pelo CEP
    cepInput.addEventListener('blur', function () {
        const cep = this.value.replace(/\D/g, '');

        if (cep.length === 8) {
            fetch(`https://viacep.com.br/ws/${cep}/json/`)
                .then(response => response.json())
                .then(data => {
                    if (!data.erro) {
                        document.getElementById('enderecorua_assistida').value = data.logradouro || '';
                        document.getElementById('enderecocidade_assistida').value = data.localidade || '';
                        document.getElementById('enderecoestado_assistida').value = data.uf || '';
                    }
                })
                .catch(() => {
                    // Sem resposta do ViaCEP, a pessoa digita o endereço à mão.
                });
        }
    });

    // Validação do formulário
    const form = document.getElementById('victimForm');

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        // Pegar o botão de submit
        const submitBtn = form.querySelector('button[type="submit"]');

        // Validações básicas
        const nome = document.getElementById('nome_assistida').value.trim();
        const apelido = document.getElementById('apelido_assistida').value.trim();
        const cpf = document.getElementById('cpf_assistida').value;
        const idade = document.getElementById('idade_assistida').value;
        const cep = document.getElementById('cep_assistida').value;
        const rua = document.getElementById('enderecorua_assistida').value.trim();
        const cidade = document.getElementById('enderecocidade_assistida').value.trim();
        const estado = document.getElementById('enderecoestado_assistida').value;
        const numero = document.getElementById('numero_assistida').value.trim();
        const complemento = document.getElementById('enderecocomplemento_assistida').value;
        const telefone = telefoneInput.value;
        const aceite = document.getElementById('aceite_aviso').checked;

        // Verificar campos obrigatórios
        if (!nome || !apelido || !cpf || !idade || !telefone || !cep || !rua || !numero || !cidade || !estado) {
            alert('Por favor, preencha todos os campos obrigatórios.');
            return;
        }

        // Validar CPF
        if (!validarCPF(cpf)) {
            alert('Por favor, digite um CPF válido.');
            return;
        }

        // Validar idade
        if (idade < 1 || idade > 120) {
            alert('Por favor, digite uma idade válida.');
            return;
        }

        // Validar telefone
        const digitosTelefone = telefone.replace(/\D/g, '').length;
        if (digitosTelefone < 10 || digitosTelefone > 11) {
            alert('Por favor, digite o telefone com DDD.');
            return;
        }

        // Validar aceite do aviso de privacidade
        if (!aceite) {
            alert('Para enviar, é preciso aceitar o aviso de privacidade.');
            return;
        }

        // Adicionar loading no botão
        if (submitBtn) {
            submitBtn.classList.add('loading');
            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Enviando...';
        }

        // Preparar os dados do formulário
        const dados = {
            cpf: cpf,
            nome: nome,
            cep: cep.replace(/\D/g, ''),
            idade: parseInt(idade),
            apelido: apelido,
            cidade: cidade,
            estado: estado,
            rua: rua,
            num_endereco: numero,
            complementoEndereco: complemento,
            telefone: telefone,
            pode_deixar_recado: document.getElementById('pode_deixar_recado').checked,
            melhor_horario: document.getElementById('melhor_horario').value.trim(),
            aceite: aceite,
            website: document.getElementById('website').value
        };

        // Enviar para a API
        fetch('/api/assistidas/adicionar/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value,
            },
            body: JSON.stringify(dados)
        })
        .then(response => response.json().catch(() => ({})).then(data => {
            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Não foi possível enviar agora.');
            }
            alert(data.message);
            window.location.href = "/";
        }))
        .catch(error => {
            alert(error.message + ' Tente novamente.');

            // Remover loading
            if (submitBtn) {
                submitBtn.classList.remove('loading');
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Enviar Cadastro';
            }
        });
    });

    // Função para validar CPF
    function validarCPF(cpf) {
        cpf = cpf.replace(/\D/g, '');

        if (cpf.length !== 11) return false;

        // Verificar se todos os dígitos são iguais
        if (/^(\d)\1{10}$/.test(cpf)) return false;

        // Validar dígitos verificadores
        let soma = 0;
        for (let i = 0; i < 9; i++) {
            soma += parseInt(cpf.charAt(i)) * (10 - i);
        }
        let resto = 11 - (soma % 11);
        let digito1 = resto > 9 ? 0 : resto;

        soma = 0;
        for (let i = 0; i < 10; i++) {
            soma += parseInt(cpf.charAt(i)) * (11 - i);
        }
        resto = 11 - (soma % 11);
        let digito2 = resto > 9 ? 0 : resto;

        return digito1 === parseInt(cpf.charAt(9)) && digito2 === parseInt(cpf.charAt(10));
    }
});