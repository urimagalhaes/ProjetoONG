// Mostra só os campos da função escolhida no formulário de equipe.
(function () {
    var form = document.getElementById('form-pessoa');
    if (!form) return;
    var opcoes = form.querySelectorAll('input[name="funcao"]');
    var campos = form.querySelectorAll('[data-funcao]');

    function atualizar() {
        var marcada = form.querySelector('input[name="funcao"]:checked');
        var funcao = marcada ? marcada.value : '';
        campos.forEach(function (campo) {
            campo.hidden = campo.dataset.funcao.split(' ').indexOf(funcao) === -1;
        });
    }

    opcoes.forEach(function (opcao) { opcao.addEventListener('change', atualizar); });
    atualizar();
})();
