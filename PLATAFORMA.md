# Plataforma e arquitetura

O AgiProz foi estruturado para utilizar a mesma aplicação em dois ambientes: desenvolvimento local e ambiente hospedado. A escolha do banco de dados é feita automaticamente a partir da variável de ambiente `DATABASE_URL`.

## Visão geral

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

A existência de `DATABASE_URL` não representa uma segunda versão da aplicação. Ela apenas informa à camada de acesso a dados qual mecanismo de persistência deve ser utilizado.

```text
┌──────────────────────────────────────────────────────────────┐
│                     db_adapter.py                            │
│                                                              │
│  DATABASE_URL não definida  ──► SQLite                       │
│  DATABASE_URL definida      ──► PostgreSQL                   │
└──────────────────────────────────────────────────────────────┘
```

Essa decisão mantém as regras de negócio concentradas na aplicação e evita duplicação de código para cada ambiente.

## Ambiente local

```text
Navegador
   ↓
Flask
   ↓
db_adapter.py
   ↓
SQLite
   ↓
instance/agiproz.sqlite3
```

Quando `DATABASE_URL` não está definida, o sistema utiliza SQLite. O diretório `instance/` é criado automaticamente quando necessário.

Esse ambiente é destinado ao desenvolvimento, testes e execução local pelo VS Code.

## Ambiente hospedado

```text
Navegador
   ↓
Render
   ↓
Gunicorn
   ↓
Flask
   ↓
db_adapter.py
   ↓
PostgreSQL
   ↓
Supabase
```

Quando `DATABASE_URL` está definida com uma conexão PostgreSQL, o adaptador utiliza `psycopg` para estabelecer a conexão com o banco.

O Render executa a aplicação com Gunicorn e fornece as variáveis de ambiente configuradas no serviço.

## Regra de seleção do banco

A regra utilizada pelo projeto é simples:

| Condição | Banco utilizado | Ambiente típico |
|---|---|---|
| `DATABASE_URL` ausente | SQLite | Desenvolvimento local |
| `DATABASE_URL` presente e válida | PostgreSQL | Render/Supabase |

Portanto, não é necessário alterar o código-fonte para alternar entre os ambientes. A configuração do ambiente determina o banco utilizado.

## Independência dos ambientes

O banco SQLite local e o banco PostgreSQL do Supabase são independentes.

```text
SQLite local  ─────── X ─────── PostgreSQL/Supabase
      │                              │
      └── não há sincronização automática ──┘
```

Isso significa que:

- um cliente criado localmente não aparece automaticamente no Supabase;
- um pagamento registrado localmente não altera o banco hospedado;
- dados criados no Supabase não são copiados automaticamente para o SQLite;
- cada ambiente possui seu próprio conjunto de dados.

## Camada de acesso a dados

O arquivo `db_adapter.py` concentra a diferença entre os dois mecanismos de banco.

Responsabilidades principais:

- identificar se `DATABASE_URL` foi configurada para PostgreSQL;
- criar e configurar a conexão SQLite quando necessário;
- abrir a conexão PostgreSQL quando necessário;
- oferecer uma interface de execução de comandos usada pela aplicação;
- tratar diferenças de parâmetros entre SQLite e PostgreSQL para as consultas utilizadas pelo projeto.

Dessa forma, `app.py` não precisa manter uma implementação separada de cada fluxo de negócio.

## Dependências

As versões utilizadas ficam registradas em `requirements.txt`. O arquivo `runtime.txt` fixa a versão do Python utilizada no deploy.

## Separação das responsabilidades

- `app.py`: rotas, autenticação, inicialização e regras de negócio.
- `db_adapter.py`: conexão e compatibilidade entre SQLite e PostgreSQL.
- `index.html`: estrutura da interface.
- `style.css`: apresentação visual.
- `app.js`: interação da interface e chamadas à API.
- `tests/`: testes automatizados.

## Fluxo de publicação

```text
Desenvolvimento local
        ↓
       Git
        ↓
     GitHub
        ↓
      Render
        ↓
 PostgreSQL/Supabase
```

O código é mantido no GitHub, o Render executa a aplicação e o Supabase fornece o banco PostgreSQL do ambiente hospedado.
