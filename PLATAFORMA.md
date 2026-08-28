# Plataforma e arquitetura

O AgiProz foi organizado para funcionar localmente e também em hospedagem.

## Ambiente local

```text
Navegador
   ↓
Flask
   ↓
SQLite
```

Quando `DATABASE_URL` não está definida, o sistema cria `instance/agiproz.sqlite3`.

## Ambiente de hospedagem

```text
Navegador
   ↓
Render + Gunicorn
   ↓
Flask
   ↓
Supabase PostgreSQL
```

Quando `DATABASE_URL` aponta para PostgreSQL, o adaptador de banco usa `psycopg`.

## Dependências

As versões utilizadas ficam registradas em `requirements.txt`. O arquivo `runtime.txt` fixa o Python usado no deploy.

## Separação das responsabilidades

- `app.py`: rotas, autenticação e regras de negócio.
- `db_adapter.py`: conexão e compatibilidade entre SQLite e PostgreSQL.
- `index.html`: estrutura da interface.
- `style.css`: apresentação visual.
- `app.js`: interação da interface e chamadas à API.
- `tests/`: testes automatizados.
