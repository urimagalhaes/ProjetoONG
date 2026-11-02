# Publicar na Vercel com Supabase

Este guia publica a branch `feat/painel` nas contas pessoais, **só com dados fictícios**. Dados reais dependem do checklist final.

Comandos em PowerShell, a partir da raiz do repositório. Valores entre `<...>` são seus. Segredos ficam só na Vercel e no seu gerenciador de senhas, nunca no Git nem em conversas.

## 1. Gerar os segredos

Use Python 3.12, a mesma versão do `.python-version`. Crie o ambiente, se ainda não existir:

```powershell
uv venv --python 3.12 venv
venv\Scripts\activate
uv pip install -r requirements.txt
```

Rode cada linha e guarde o resultado com o nome ao lado.

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"                                # SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # CHAVES_CIFRAGEM
python -c "import secrets; print(secrets.token_urlsafe(50))"                                # CHAVE_HASH_CPF
python -c "import secrets; print(secrets.token_urlsafe(32))"                                # CRON_SECRET
```

**Perder `CHAVES_CIFRAGEM` significa perder CPF, endereço, telefone e prontuários. Perder `CHAVE_HASH_CPF` quebra a busca por CPF e a detecção de repetidos.**

## 2. Criar o banco no Supabase

1. Crie um **projeto novo** na região `South America (São Paulo)`, `sa-east-1`. Não reaproveite os dois pausados. Guarde a senha do banco.
2. Em **Project Settings > Data API**, desative a Data API. O sistema só acessa o banco pelo Django.
3. Em **Connect**, copie as duas URLs do pooler:
   - **Transaction pooler**, porta `6543`: é o `DATABASE_URL` da Vercel;
   - **Session pooler**, porta `5432`: usada só nas migrations.

Se a senha do banco tiver caracteres especiais, ela precisa estar codificada na URL (`@` vira `%40`). Mais simples: use uma senha só com letras e números, longa.

## 3. Criar as tabelas e o superusuário

Rode dentro de `back-end`. As variáveis ficam só nesta janela do PowerShell.

```powershell
cd back-end
$env:DEBUG = "False"
$env:SECRET_KEY = "<SECRET_KEY>"
$env:CHAVES_CIFRAGEM = "<CHAVES_CIFRAGEM>"
$env:CHAVE_HASH_CPF = "<CHAVE_HASH_CPF>"
$env:DATABASE_URL = "<URL do Session pooler>"
python manage.py migrate
python manage.py createsuperuser
```

Feche a janela ao terminar. Use senha forte. `admin` / `admin` existe só na sua máquina, e o `seed_dev` não roda em produção.

## 4. Publicar

```powershell
cd ..
npx vercel login
npx vercel link
```

Quando perguntar, crie um projeto novo e mantenha o diretório `./` (a raiz do repositório). Depois abra o projeto no painel da Vercel e, em **Settings > Environment Variables**, crie estas variáveis para **Production**:

| Variável | Valor |
| --- | --- |
| `SECRET_KEY` | gerado no passo 1 |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `<projeto>.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://<projeto>.vercel.app` |
| `DATABASE_URL` | URL do Transaction pooler |
| `CHAVES_CIFRAGEM` | gerado no passo 1 |
| `CHAVE_HASH_CPF` | gerado no passo 1 |
| `CRON_SECRET` | gerado no passo 1 |

Publique:

```powershell
npx vercel --prod
```

O build acontece nos servidores da Vercel. Não use `vercel build` no Windows: ele baixa pacotes de Linux, e o `cryptography` falha nesse passo.

Se o domínio final for outro, corrija `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` e publique de novo. O `collectstatic` é executado pela Vercel, e `.vercelignore` impede o envio do `.env`, do `db.sqlite3` e do `CLAUDE.md`.

## 5. Ajustar a proteção

- **Deployment Protection:** deixe em **Standard Protection** com Vercel Authentication. Isso protege as URLs de preview e mantém o site público no ar. **All Deployments** bloquearia o site para quem não tem conta na Vercel.
- **Firewall:** crie uma regra custom do tipo Challenge para os caminhos `/api/assistidas/adicionar/` e os que começam com `/api/voluntarios/`, para frear robôs nos cadastros.

## 6. Primeiro acesso

1. Abra `https://<projeto>.vercel.app/entrar/` e entre com o superusuário.
2. Troque a senha e leia o código QR com um aplicativo autenticador. **Sem o celular não há como entrar:** quem recupera 2FA é outro superusuário, em **Administração > TOTP devices**, então crie dois superusuários.
3. Em `/painel/`, abra **Equipe > Adicionar à equipe** e preencha um formulário só. Ele cria o cadastro e o login, e mostra a senha temporária uma vez. Marque "Também pode usar este painel" para quem é da coordenação.
4. Cadastre assistidas fictícias pelo formulário público ou em **Assistidas > Nova assistida**.
5. Na página da assistida, escolha quem atende. Sem atendente, ninguém abre o prontuário, nem a coordenação nem o superusuário.
6. Quem é da coordenação e também atende usa **Também vou atender** no painel, com o próprio login.

## 7. Conferir

Depois de publicar:

```powershell
curl.exe -i -H "Authorization: Bearer <CRON_SECRET>" https://<projeto>.vercel.app/manutencao/banco/
```

A resposta deve ser `200` com `{"ok": true}`. Sem o cabeçalho, `404`.

- [ ] A página inicial e o formulário de cadastro abrem com estilo e fontes.
- [ ] Um cadastro fictício aparece em `/painel/assistidas/`.
- [ ] No **Table Editor** do Supabase, CPF e texto do prontuário aparecem começando com `gAAAA`.
- [ ] Atendente sem vínculo recebe 404 no prontuário.
- [ ] **Settings > Cron Jobs** mostra a rota `/manutencao/banco/`.
- [ ] Em **Usage**, acompanhe o uso de CPU depois de alguns acessos. O limite do Hobby é de 4 horas por mês.

## Se algo der errado

- **Erro 400:** o domínio não está em `ALLOWED_HOSTS`.
- **Erro 403 ao enviar formulário:** o domínio com `https://` não está em `CSRF_TRUSTED_ORIGINS`.
- **Erro `Defina CHAVES_CIFRAGEM e CHAVE_HASH_CPF`:** faltam as variáveis no ambiente Production.
- **Erro `InvalidToken`:** a chave usada não é a mesma que cifrou os dados.
- **Conexão recusada no `migrate`:** use a URL do Session pooler. A conexão direta só funciona por IPv6.
- **Conta bloqueada:** cinco senhas erradas travam o login por 30 minutos.
- **Plano B:** o `Dockerfile` continua válido para a Fly.io, em São Paulo.

## Antes de qualquer dado real

Nada disto é código, e todos os itens são obrigatórios.

- [ ] Vercel confirmar se o plano Hobby serve à ONG. Se não, migrar para a Fly.io ou assinar o Pro.
- [ ] Criar contas da própria ONG e tornar o repositório privado.
- [ ] Ter backup diário cifrado, com restauração testada. O Supabase Free não faz backup.
- [ ] Guardar as chaves com duas pessoas, fora do sistema.
- [ ] Validar com jurídico: base legal, aviso de privacidade, RIPD, encarregado e o contrato de tratamento de dados do Supabase (`privacy@supabase.io`).
- [ ] Completar `/privacidade/` com CNPJ e contato.
- [ ] Identificar o dono do IP que recebia os dados de voluntários.
- [ ] Definir como digitalizar o caderno.
