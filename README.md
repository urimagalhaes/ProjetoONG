# Superação da Violência Doméstica — Sistema de Gestão

Sistema web desenvolvido para uma ONG que acolhe e orienta **mulheres em situação de violência doméstica**. Reúne em um só lugar o site institucional, o cadastro de **assistidas** e de **voluntários** (advogados, bacharéis e estagiários), o agendamento de **atendimentos** e o **prontuário** de cada assistida, escrito pelos profissionais que a atenderam.

> **Aviso:** o sistema lida com dados pessoais sensíveis (LGPD). Nunca publique um banco de dados real, o arquivo `.env` ou credenciais neste repositório. Veja [Segurança e privacidade](#segurança-e-privacidade).

---

## Sumário

- [Funcionalidades](#funcionalidades)
- [Tecnologias](#tecnologias)
- [Como executar localmente](#como-executar-localmente)
- [Endereços do sistema](#endereços-do-sistema)
- [Testes](#testes)
- [Configuração (variáveis de ambiente)](#configuração-variáveis-de-ambiente)
- [Docker e deploy](#docker-e-deploy)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Modelo de dados](#modelo-de-dados)
- [Segurança e privacidade](#segurança-e-privacidade)
- [Limitações conhecidas e próximos passos](#limitações-conhecidas-e-próximos-passos)
- [Como contribuir](#como-contribuir)
- [Equipe e licença](#equipe-e-licença)

---

## Funcionalidades

**Já disponíveis**

- **Site institucional:** página inicial, notícias, programa de voluntários e páginas de cadastro.
- **Cadastro de assistidas:** formulário público com preenchimento automático do endereço pelo CEP.
- **Cadastro de voluntários:** formulários separados para advogado, bacharel e estagiário, com a disponibilidade semanal dos estagiários.
- **Painel de administração** (`/admin/`): cadastros, voluntários, atendimentos, vínculos, usuários, registro de acessos e direitos da titular. **Não dá acesso a prontuários.**
- **Lista de assistidas:** mostra só as assistidas vinculadas a quem está logado, com busca por nome, apelido ou CPF completo.
- **Prontuário da assistida:** só abre com vínculo ativo, inclusive para a coordenação e para superusuários. O autor vem do login; só ele edita, e cada edição guarda o texto anterior.
- **Segurança:** dados pessoais cifrados no banco, registro de acessos, login com 2FA e bloqueio de tentativas.
- **Dados de exemplo** para testes locais (`seed_dev`) e **suíte de testes automatizados**.

**Em desenvolvimento:** agendamento de atendimentos pela API e envio de documentos (veja o [roadmap](#limitações-conhecidas-e-próximos-passos)).

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Linguagem / framework | Python 3.12 · Django 5.2 LTS · Django REST Framework |
| Banco de dados | SQLite (desenvolvimento) · PostgreSQL (produção, via `DATABASE_URL`) |
| Front-end | HTML, CSS e JavaScript servidos pelo próprio Django (templates e estáticos) |
| Servidor | Gunicorn + WhiteNoise |
| Empacotamento / deploy | Vercel · Docker |
| Configuração | python-decouple · dj-database-url |

## Como executar localmente

Pré-requisito: **Python 3.12** instalado. Os comandos abaixo são para o terminal na pasta do projeto.

**Windows (PowerShell)**

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
cd back-end
python manage.py migrate
python manage.py seed_dev
python manage.py runserver
```

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd back-end
python3 manage.py migrate
python3 manage.py seed_dev
python3 manage.py runserver
```

Abra <http://127.0.0.1:8000>.

O comando `seed_dev` cria dados **fictícios** (assistidas, voluntários e prontuários) o usuário de teste **`admin` / `admin`** e logins com senha igual ao nome: `coordenadora`, `helena`, `paula` e `carlos`. Ele só funciona com `DEBUG=True` e pode ser repetido sem duplicar registros. Para usar um usuário próprio, rode `python manage.py createsuperuser`.

> Em cada novo terminal, ative o ambiente virtual antes de rodar os comandos (`venv\Scripts\activate` no Windows, `source venv/bin/activate` no macOS/Linux). O prompt deve começar com `(venv)`.

## Endereços do sistema

| O quê | Endereço | Acesso |
|---|---|---|
| Site institucional | `/` | Público |
| Cadastro de assistida | `/cadastro-assistida/` | Público |
| Programa de voluntários | `/voluntarios/` | Público |
| Entrar | `/entrar/` | Equipe |
| Lista de assistidas | `/assistidas/` | Login; mostra só as vinculadas |
| Prontuário da assistida | `/assistidas/<id>/prontuario/` | Só com vínculo ativo |
| Administração | `/admin/` | Coordenação |
| API: cadastrar assistida (`POST` JSON) | `/api/assistidas/adicionar/` | Público |
| API: cadastrar voluntário (`POST` JSON) | `/api/voluntarios/adicionar/{estagiario,advogado,bacharel}/` | Público |

As regras de acesso ficam em `back-end/assistidas/permissoes.py`.

## Testes

```bash
cd back-end
python manage.py test
```

A suíte cobre o cadastro pela API, as páginas internas, o controle de acesso ao prontuário, a validação do formulário, a proteção CSRF, o escape de HTML digitado nos registros e as regras dos atendimentos. Rode antes de enviar qualquer alteração. Se mudar um model, gere a migration com `python manage.py makemigrations` e confirme com `python manage.py makemigrations --check` que não restou nada pendente.

## Configuração (variáveis de ambiente)

Copie `.env.example` para `.env` (o arquivo `.env` **não** vai para o Git).

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `SECRET_KEY` | Sim | — | Chave secreta do Django. Use um valor longo e aleatório em produção. |
| `DEBUG` | Não | `False` | `True` apenas em desenvolvimento. |
| `ALLOWED_HOSTS` | Não | `localhost,127.0.0.1` | Domínios aceitos, separados por vírgula. |
| `DATABASE_URL` | Não | SQLite local | Ex.: `postgres://usuario:senha@host:5432/banco`. |
| `CHAVES_CIFRAGEM` | Só com `DEBUG=False` | chave de desenvolvimento | Chaves Fernet separadas por vírgula. A primeira cifra; as demais só decifram. |
| `CHAVE_HASH_CPF` | Só com `DEBUG=False` | chave de desenvolvimento | Chave do hash usado na busca e na unicidade do CPF. |
| `CSRF_TRUSTED_ORIGINS` | Em produção | vazio | Domínios com `https://`, separados por vírgula. |
| `CRON_SECRET` | Em produção | vazio | Protege a rota do cron diário. Vazio desliga a rota. |
| `EXIGIR_2FA` | Não | contrário de `DEBUG` | Exige o segundo fator na área interna. |

## Docker e deploy

```bash
docker compose up --build        # http://localhost:8000
docker compose exec web python manage.py seed_dev
```

O `Dockerfile` instala as dependências, coleta os arquivos estáticos e inicia o `entrypoint.sh`, que aplica as migrations e sobe o Gunicorn. Serve para rodar localmente e como alternativa de hospedagem.

A publicação na Vercel com Supabase está em [`docs/deploy-vercel.md`](docs/deploy-vercel.md).

## Estrutura do projeto

```
ProjetoONG/
├── back-end/
│   ├── server/          configurações, urls e wsgi
│   ├── core/            páginas do site, login, 2FA, criptografia e o comando seed_dev
│   ├── assistidas/      Assistida, prontuário, vínculos, auditoria, permissões e direitos da titular
│   ├── voluntarios/     Voluntario, Estagiario, Advogado, Bacharel, Disponibilidade
│   ├── atendimentos/    Atendimento (API ainda em rascunho)
│   ├── manage.py
│   └── entrypoint.sh
├── Dockerfile
├── docs/deploy-vercel.md
├── docker-compose.yml
├── railway.toml
├── vercel.json
├── requirements.txt
└── .env.example
```

## Modelo de dados

- **Assistida:** CPF, nome, apelido, idade, contato e endereço completo. CPF, contato e endereço são cifrados; a unicidade usa um hash do CPF.
- **VinculoAtendimento:** liga voluntário e assistida, com início e fim. É a única fonte da regra de acesso ao prontuário.
- **RegistroAcesso:** trilha de quem leu, criou, editou, exportou ou teve acesso negado. Só recebe inclusões e nunca guarda o conteúdo.
- **RegistroProntuario:** pertence a uma assistida e a um voluntário (o profissional que escreveu). Guarda o texto, a data de criação e a de atualização. É um histórico: novos registros se somam aos anteriores. Um voluntário que já escreveu em um prontuário não pode ser apagado.
- **Voluntario:** dados pessoais e de contato. Especializa-se em **Estagiario** (curso, período e disponibilidade semanal), **Advogado** (OAB) e **Bacharel** (curso de formação).
- **Atendimento:** liga uma assistida, um estagiário, uma data e um horário.

## Segurança e privacidade

- As páginas de lista e de prontuário exigem login e vínculo, e enviam cabeçalhos para **não ficar em cache** do navegador. Sem permissão, a resposta é 404.
- CPF, RG, telefone, endereço e texto do prontuário ficam cifrados no banco. Perder as chaves significa perder esses dados.
- Em produção, a área interna exige 2FA e bloqueia a conta por 30 minutos após 5 senhas erradas.
- O texto dos registros é escapado na exibição, o que impede a injeção de HTML ou script.
- O formulário do prontuário é protegido contra CSRF.
- O `.gitignore` mantém de fora `.env`, `db.sqlite3` e `venv/`. **Nunca** faça commit de bancos de dados, de documentos das assistidas ou de chaves.
- Como o sistema trata dados de saúde e de violência, seu uso real exige o checklist do fim de [`docs/deploy-vercel.md`](docs/deploy-vercel.md): base legal, RIPD, encarregado e backup cifrado.

## Limitações conhecidas e próximos passos

- [ ] **Limite de requisições:** os cadastros públicos têm só campo-isca. O limite depende de regra no firewall da hospedagem.
- [ ] **Documentos e fotos:** hoje o sistema guarda apenas se o documento foi enviado (verdadeiro ou falso). O plano é guardar os arquivos em armazenamento de objetos **privado** (por exemplo S3 ou Cloudflare R2), com acesso por link temporário, e manter no banco só o caminho.
- [ ] **API de atendimentos:** faltam o agendamento e a tela para cadastrar a disponibilidade dos estagiários.

## Como contribuir

1. Crie um branch a partir do principal: `git checkout -b feature/nome-da-melhoria`.
2. Faça as alterações e rode `python manage.py test` até terminar com `OK`.
3. Faça o commit com uma mensagem clara e abra um *pull request*.

## Equipe e licença

- **Equipe:** _preencha com os nomes e contatos dos integrantes._
- **Licença:** _a definir._ Enquanto não houver uma licença, todos os direitos ficam reservados aos autores.

