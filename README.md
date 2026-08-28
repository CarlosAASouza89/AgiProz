# AgiProz

Sistema acadêmico para controle de clientes, empréstimos, parcelas, pagamentos, usuários e comunicação interna.

## Tecnologias

- Python 3.12
- Flask
- SQLite para uso local
- PostgreSQL para hospedagem
- HTML, CSS e JavaScript no frontend
- Gunicorn para execução no Render
- Supabase como banco PostgreSQL

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
└── documentação
```

## Execução local

1. Instale o Python 3.12.
2. Crie um ambiente virtual:

```bash
python -m venv .venv
```

3. Ative o ambiente virtual.
4. Instale as dependências:

```bash
pip install -r requirements.txt
```

5. Inicie a aplicação:

```bash
python app.py
```

6. Acesse `http://127.0.0.1:5500`.

Sem `DATABASE_URL`, o sistema utiliza SQLite e cria o banco em `instance/agiproz.sqlite3`.

## Primeiro acesso

O banco inicia sem usuários. Na primeira abertura, crie o administrador com um e-mail no domínio `@agiproz.local` e uma senha com:

- pelo menos 8 caracteres;
- uma letra maiúscula;
- um número;
- um caractere especial;
- nenhum espaço.

A chave de recuperação do administrador é exibida após o cadastro e novamente após cada recuperação, sempre com rotação da chave anterior. No ambiente local, uma cópia também é gravada em `instance/admin_recovery_code.txt`. No ambiente hospedado com Supabase/Render, não há arquivo local para essa chave; ela deve ser guardada em local seguro. O diretório `instance/` não deve ser enviado ao GitHub.

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
GitHub → Render → Supabase PostgreSQL
```

Consulte `DEPLOY_SUPABASE_RENDER.md` para o passo a passo.

Nunca envie para o GitHub:

- `.env`;
- `instance/`;
- bancos SQLite;
- senhas;
- `DATABASE_URL`;
- chaves de recuperação.

## Observação acadêmica

O AgiProz é um projeto acadêmico e demonstrativo. Os limites, taxas e regras de cálculo existentes no sistema não representam uma política de uma instituição financeira real.
