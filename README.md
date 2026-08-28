# AgiProz

Sistema acadêmico para controle de clientes, empréstimos, parcelas, pagamentos, usuários e comunicação interna.

## Tecnologias

- Python 3.12
- Flask
- SQLite para desenvolvimento local
- PostgreSQL para o ambiente hospedado
- HTML, CSS e JavaScript no frontend
- Gunicorn para execução no Render
- Supabase como serviço de banco PostgreSQL

## Arquitetura de execução

O AgiProz utiliza a mesma aplicação nos dois ambientes. A diferença está no banco de dados utilizado pela camada de acesso a dados.

```text
                         AGIPROZ
                            │
                    DATABASE_URL?
                            │
              ┌─────────────┴─────────────┐
              │                           │
             NÃO                         SIM
              │                           │
              ▼                           ▼
          SQLite local              PostgreSQL
              │                           │
              ▼                           ▼
       VS Code + Flask             Supabase + Render
```

A variável `DATABASE_URL` é o mecanismo que determina qual banco será utilizado:

```text
DATABASE_URL não definida
        │
        ▼
SQLite
instance/agiproz.sqlite3

DATABASE_URL definida
        │
        ▼
PostgreSQL
Supabase
```

Essa abordagem evita manter duas implementações da aplicação. O arquivo `db_adapter.py` concentra a diferença de conexão e compatibilidade entre SQLite e PostgreSQL, enquanto as regras de negócio permanecem na aplicação.

Os dois ambientes possuem bancos independentes. Dados cadastrados no SQLite local não são enviados automaticamente ao Supabase, e dados do Supabase não são copiados automaticamente para o SQLite local.

## Estrutura

```text
AgiProz/
├── app.py
├── db_adapter.py
├── app.js
├── index.html
├── style.css
├── assets/
├── tests/
├── requirements.txt
├── render.yaml
├── Procfile
├── runtime.txt
├── .env.example
├── README.md
├── PLATAFORMA.md
├── COMO_INICIAR.md
├── DEPLOY_SUPABASE_RENDER.md
├── GITHUB_PASSO_A_PASSO.md
└── GUIA-CODIGO.md
```

## Requisitos

### Desenvolvimento local

- Windows 10/11;
- Python 3.12;
- VS Code (recomendado);
- navegador web atualizado.

### Ambiente hospedado

- conta no GitHub;
- projeto no Supabase;
- serviço no Render.

## Execução local

1. Instale o Python 3.12.
2. Abra a pasta do projeto no VS Code.
3. Abra `Terminal → Novo Terminal`.
4. Crie um ambiente virtual:

```bash
python -m venv .venv
```

5. Ative o ambiente virtual.
6. Instale as dependências:

```bash
pip install -r requirements.txt
```

7. Inicie a aplicação:

```bash
python app.py
```

8. Acesse `http://127.0.0.1:5500`.

Por padrão, a execução local não exige `DATABASE_URL`. Sem essa variável, o sistema utiliza SQLite e cria o banco em `instance/agiproz.sqlite3`.

Para executar localmente usando PostgreSQL, configure `DATABASE_URL` antes de iniciar a aplicação. Nesse caso, o SQLite local não será utilizado.

## Banco local

Quando o AgiProz é executado sem `DATABASE_URL`, o banco SQLite fica em:

```text
instance/agiproz.sqlite3
```

A pasta `instance/` contém dados específicos do ambiente local e não deve ser enviada ao GitHub. O `.gitignore` do projeto já impede o versionamento dessa pasta e dos arquivos de banco local.

## Primeiro acesso

O banco inicia sem usuários. Na primeira abertura, crie o administrador com um e-mail no domínio `@agiproz.local` e uma senha com:

- pelo menos 8 caracteres;
- uma letra maiúscula;
- um número;
- um caractere especial;
- nenhum espaço.

A chave de recuperação do administrador é exibida após o cadastro e novamente após cada recuperação, sempre com rotação da chave anterior. No ambiente local, uma cópia também é gravada em `instance/admin_recovery_code.txt`. No ambiente hospedado com Supabase/Render, não há arquivo local para essa chave; ela deve ser guardada em local seguro.

## Usuários

O administrador pode criar, editar, ativar, desativar e redefinir operadores.

Ao criar ou redefinir um operador, o sistema gera uma senha temporária aleatória. Ela é exibida ao administrador e deve ser entregue ao operador. No primeiro acesso, o operador precisa escolher uma nova senha.

## Empréstimos

O sistema trabalha com três periodicidades:

- semanal: 7 dias;
- quinzenal: 14 dias;
- mensal: mantém o dia de referência sempre que possível e utiliza o último dia do mês quando o mês não possui esse dia.

Exemplo: um contrato iniciado em 31/01 gera 28/02, 31/03 e 30/04.

As datas são gravadas nas parcelas no momento da criação do contrato. Pagamentos e atrasos não alteram o calendário.

## Pagamentos

Cada parcela possui seu próprio registro. O pagamento é feito na ordem das parcelas e uma parcela não pode receber dois pagamentos simultâneos.

Para fins acadêmicos, o atraso utiliza juros simples de 10% ao dia sobre o valor original da parcela. Os cálculos são feitos com `Decimal` e arredondamento para centavos.

## Comunicação interna

As mensagens utilizam endereços `@agiproz.local` e permanecem dentro da aplicação. Não existe envio de e-mail para a Internet.

## Auditoria

Operações administrativas e alterações relevantes são registradas em `audit_logs`, permitindo consultar usuário, ação, entidade, registro e data.

## Testes

Execute:

```bash
python -m unittest discover -s tests -v
```

Os testes cobrem o primeiro acesso, autenticação, usuários, empréstimos, calendário de parcelas, pagamentos, recuperação de senha e auditoria.

## GitHub, Supabase e Render

A configuração recomendada para a publicação é:

```text
VS Code
   ↓
Git
   ↓
GitHub
   ↓
Render ──────────┐
   ↓             │
Flask/Gunicorn   │
                 ▼
          PostgreSQL
                 ↓
              Supabase
```

No ambiente hospedado, `DATABASE_URL` deve conter a conexão PostgreSQL do Supabase. O Render fornece essa variável à aplicação durante a execução.

Consulte `DEPLOY_SUPABASE_RENDER.md` para o passo a passo de implantação.

Nunca envie para o GitHub:

- `.env`;
- `instance/`;
- bancos SQLite;
- senhas;
- `DATABASE_URL` com credenciais;
- chaves de recuperação;
- chaves secretas.

## Documentação do projeto

- `PLATAFORMA.md`: arquitetura e funcionamento dos ambientes local e hospedado.
- `COMO_INICIAR.md`: execução local pelo VS Code.
- `DEPLOY_SUPABASE_RENDER.md`: implantação no Supabase e Render.
- `GITHUB_PASSO_A_PASSO.md`: publicação e organização do código no GitHub.
- `GUIA-CODIGO.md`: descrição dos principais arquivos e componentes.
- `casos-de-teste.md`: cenários utilizados na validação da aplicação.

## Observação acadêmica

O AgiProz é um projeto acadêmico e demonstrativo. Os limites, taxas e regras de cálculo existentes no sistema não representam uma política de uma instituição financeira real.
