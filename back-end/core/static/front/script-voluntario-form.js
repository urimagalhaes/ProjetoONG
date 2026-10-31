document.addEventListener('DOMContentLoaded', function () {
    const cpfInput = document.getElementById('cpf_voluntario');
    const rgInput = document.getElementById('rg_voluntario');
    const telefoneInput = document.getElementById('telefone_voluntario');
    const oabInput = document.getElementById('oab_voluntarioadvogado');


    if (cpfInput) {
        cpfInput.addEventListener('input', function (e) {
            let value = e.target.value.replace(/\D/g, '');
            value = value.replace(/(\d{3})(\d)/, '$1.$2');
            value = value.replace(/(\d{3})(\d)/, '$1.$2');
            value = value.replace(/(\d{3})(\d{1,2})$/, '$1-$2');
            e.target.value = value;
        });
    }

    if (rgInput) {
        rgInput.addEventListener('input', function (e) {
            let value = e.target.value.replace(/\D/g, '');
            e.target.value = value;
        });
    }


    if (telefoneInput) {
        telefoneInput.addEventListener('input', function (e) {
            let value = e.target.value.replace(/\D/g, '');
            e.target.value = value;
        });
    }


    if (oabInput) {
        oabInput.addEventListener('input', function (e) {
            let value = e.target.value.toUpperCase();
            value = value.replace(/[^A-Z0-9]/g, '');
            if (value.length > 2) {
                value = value.substring(0, 2) + '/' + value.substring(2, 8);
            }
            e.target.value = value;
        });
    }

    const dataNascInput = document.getElementById('datanasc_voluntario');
    if (dataNascInput) {
        dataNascInput.addEventListener('change', function () {
            const hoje = new Date();
            const nascimento = new Date(this.value);
            const idade = hoje.getFullYear() - nascimento.getFullYear();
            const mesAtual = hoje.getMonth();
            const mesNascimento = nascimento.getMonth();

            let idadeReal = idade;
            if (mesAtual < mesNascimento || (mesAtual === mesNascimento && hoje.getDate() < nascimento.getDate())) {
                idadeReal--;
            }

            if (idadeReal < 18) {
                this.setCustomValidity('Você deve ter pelo menos 18 anos para se voluntariar.');
                showError(this, 'Você deve ter pelo menos 18 anos para se voluntariar.');
            } else {
                this.setCustomValidity('');
                clearError(this);
            }
        });
    }

    const form = document.getElementById('volunteerForm');

    form.addEventListener('submit', function (e) {
        e.preventDefault();


        clearAllErrors();

        let isValid = true;


        const requiredFields = form.querySelectorAll('[required]');
        requiredFields.forEach(field => {
            const preenchido = field.type === 'checkbox' ? field.checked : field.value.trim();
            if (!preenchido) {
                showError(field, 'Este campo é obrigatório.');
                isValid = false;
            }
        });

        if (cpfInput && !validarCPF(cpfInput.value)) {
            showError(cpfInput, 'CPF inválido.');
            isValid = false;
        }

        if (rgInput && rgInput.value.length !== 9) {
            showError(rgInput, 'RG deve ter 9 dígitos.');
            isValid = false;
        }

        if (telefoneInput && telefoneInput.value.length !== 9) {
            showError(telefoneInput, 'Telefone deve ter 9 dígitos.');
            isValid = false;
        }

        if (oabInput && !validarOAB(oabInput.value)) {
            showError(oabInput, 'Formato de OAB inválido. Use: UF/123456');
            isValid = false;
        }

        if (isValid) {
            const submitBtn = form.querySelector('.submit-btn');
            submitBtn.classList.add('loading');
            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Enviando... <span class="loading-spinner"></span>';


            const dados = {
                nome: document.getElementById('nomecompleto_voluntario').value,
                email: document.getElementById('email_voluntario').value,
                dataNascimento: document.getElementById('datanasc_voluntario').value,
                sexo: document.getElementById('sexo_voluntario').value,
                cpf: document.getElementById('cpf_voluntario').value.replace(/\D/g, ''), // Remove pontos e traços
                rg: document.getElementById('rg_voluntario').value,
                telefone: document.getElementById('telefone_voluntario').value,
                instagram: document.getElementById('instagram_voluntario').value,
                endereco: document.getElementById('enderecorua_voluntario').value,
                cidade: document.getElementById('enderecocidade_voluntario').value,
                estado: document.getElementById('enderecoestado_voluntario').value || '',
                aceite: document.getElementById('aceite_aviso').checked,
                website: document.getElementById('website').value
            };

            let rota = '/api/voluntarios/adicionar/estagiario/';
            const oab = document.getElementById('oab_voluntarioadvogado');
            const cursoBacharel = document.getElementById('cursoformacao_voluntariobacharel');
            const cursoEstagiario = document.getElementById('cursonome_voluntarioestagiario');

            if (oab) {
                dados.oab = oab.value;
                rota = '/api/voluntarios/adicionar/advogado/';
            } else if (cursoBacharel) {
                dados.cursoBacharel = cursoBacharel.value;
                rota = '/api/voluntarios/adicionar/bacharel/';
            } else if (cursoEstagiario) {
                dados.curso = cursoEstagiario.value;
                dados.periodo = document.getElementById('cursoperido_voluntarioestagiario').value;
            }

            fetch(rota, {
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
                    window.location.href = '/voluntarios/';
                }))
                .catch(error => {
                    alert(error.message + ' Tente novamente.');

                    submitBtn.classList.remove('loading');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Enviar Cadastro';
                });
        } else {

            const firstError = form.querySelector('.form-group.error');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

    });


    function showError(field, message) {
        const formGroup = field.closest('.form-group');
        formGroup.classList.add('error');

        let errorElement = formGroup.querySelector('.error-message');
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'error-message';
            formGroup.appendChild(errorElement);
        }
        errorElement.textContent = message;
    }

    function clearError(field) {
        const formGroup = field.closest('.form-group');
        formGroup.classList.remove('error');
        const errorElement = formGroup.querySelector('.error-message');
        if (errorElement) {
            errorElement.remove();
        }
    }

    function clearAllErrors() {
        const errorGroups = form.querySelectorAll('.form-group.error');
        errorGroups.forEach(group => {
            group.classList.remove('error');
            const errorElement = group.querySelector('.error-message');
            if (errorElement) {
                errorElement.remove();
            }
        });
    }

    function validarCPF(cpf) {
        cpf = cpf.replace(/\D/g, '');

        if (cpf.length !== 11) return false;
        if (/^(\d)\1{10}$/.test(cpf)) return false;

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

    function validarOAB(oab) {
        const regex = /^[A-Z]{2}\/[0-9]{6}$/;
        return regex.test(oab);
    }


    const formElements = document.querySelectorAll('.form-group');
    formElements.forEach((element, index) => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(20px)';
        element.style.transition = 'opacity 0.5s ease, transform 0.5s ease';

        setTimeout(() => {
            element.style.opacity = '1';
            element.style.transform = 'translateY(0)';
        }, index * 50);
    });
});