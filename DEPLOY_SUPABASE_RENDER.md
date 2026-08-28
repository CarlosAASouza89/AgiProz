# Deploy do AgiProz com GitHub, Supabase e Render

Este documento descreve a implantação do ambiente hospedado do AgiProz.

A execução local continua disponível e utiliza SQLite quando `DATABASE_URL` não está definida. No ambiente hospedado, `DATABASE_URL` aponta para o PostgreSQL do Supabase.

## Arquitetura do deploy

```text
                         AGIPROZ
                            │
                     DATABASE_URL
                            │
                            ▼
                     PostgreSQL
                            │
                         Supabase
                            ▲
                            │
                         Render
                            │
                         Gunicorn
                            │
                          Flask
```

A variável `DATABASE_URL` é o ponto de configuração que faz a aplicação utilizar PostgreSQL no ambiente hospedado.

```text
LOCAL
DATABASE_URL ausente
        ↓
     SQLite

HOSPEDADO
DATABASE_URL presente
        ↓
    PostgreSQL
        ↓
    Supabase
```

## 1. Criar o banco no Supabase

1. Crie um projeto no Supabase.
2. Abra a área de conexão do banco.
3. Copie uma URL PostgreSQL adequada para uma aplicação de servidor.
4. Mantenha a URL em segredo.
5. Se a URL fornecida pelo Supabase não trouxer SSL, utilize uma configuração com `sslmode=require`.

O AgiProz cria as tabelas necessárias automaticamente na inicialização do banco.

### Atenção à senha do banco

A senha presente na `DATABASE_URL` deve corresponder à senha atual do usuário PostgreSQL do projeto Supabase.

Se o Render apresentar uma mensagem semelhante a:

```text
password authentication failed for user "postgres"
```

verifique a senha e a `DATABASE_URL` configuradas no Render. Se necessário, gere uma nova string de conexão no Supabase e atualize a variável no Render.

Nunca publique a `DATABASE_URL` no GitHub, em capturas de tela ou em documentação.

## 2. Preparar o GitHub

Na pasta do projeto:

```bash
git init
git add .
git commit -m "Preparar projeto para deploy"
git branch -M main
git remote add origin URL_DO_REPOSITORIO
git push -u origin main
```

Antes do `git add .`, confirme que `.env`, `instance/` e bancos SQLite estão ignorados pelo `.gitignore`.

## 3. Criar o serviço no Render

O projeto já possui `render.yaml`.

Ao utilizar o Blueprint, a configuração do projeto define:

- runtime Python;
- `pip install -r requirements.txt` como comando de build;
- Gunicorn como servidor da aplicação;
- `/api/bootstrap` como health check;
- `AGIPROZ_SECRET_KEY` gerada automaticamente pelo Render;
- `DATABASE_URL` informada pelo usuário;
- `SESSION_COOKIE_SECURE=1` para o ambiente HTTPS.

Configure as variáveis de ambiente:

```text
DATABASE_URL = URL PostgreSQL do Supabase
AGIPROZ_SECRET_KEY = chave longa e aleatória
SESSION_COOKIE_SECURE = 1
```

O `render.yaml` já solicita ao Render a geração automática de `AGIPROZ_SECRET_KEY` quando o serviço é criado por Blueprint.

## 4. Primeiro acesso no Render

Depois que o serviço estiver com status de execução normal:

1. Abra a URL fornecida pelo Render.
2. Crie o administrador.
3. Copie a chave de recuperação apresentada pela aplicação.
4. Guarde a chave em local seguro.

No ambiente PostgreSQL, o sistema não depende de um arquivo local para armazenar a chave de recuperação. O arquivo `instance/admin_recovery_code.txt` é uma característica do modo local e não deve ser utilizado como mecanismo de armazenamento no servidor.

## 5. Verificação após o deploy

Depois da publicação, valide os principais fluxos:

1. A página inicial abre normalmente.
2. O primeiro acesso permite criar o administrador.
3. O login funciona.
4. O logout funciona.
5. É possível cadastrar um cliente.
6. É possível criar um empréstimo.
7. As parcelas são geradas corretamente.
8. É possível registrar um pagamento.
9. A auditoria registra as operações relevantes.
10. A aplicação continua respondendo após novo acesso.

## 6. Problemas comuns

### `password authentication failed`

Verifique a senha e a `DATABASE_URL` do PostgreSQL no Render. A conexão deve utilizar as credenciais atuais do Supabase.

### `Application failed to respond`

Verifique os logs do Render e confirme se o comando do Gunicorn está sendo executado corretamente.

### `ModuleNotFoundError`

Verifique `requirements.txt` e confirme se todas as dependências foram instaladas durante o build.

### Erro de tabela inexistente

Verifique se a inicialização do banco foi executada corretamente e se a aplicação conseguiu conectar ao PostgreSQL.

## 7. Trabalho acadêmico em equipe

Recomenda-se que cada integrante trabalhe em uma branch própria:

```text
main
└── feature/nome-da-tarefa
```

Depois, abra um Pull Request para revisão antes de juntar a alteração à `main`.

## 8. Cuidados antes de publicar

Nunca coloque no repositório:

- `.env`;
- `DATABASE_URL` com credenciais;
- senhas;
- banco SQLite com dados pessoais;
- chave de recuperação;
- chaves secretas;
- arquivos da pasta `instance/`.

## 9. Relação entre desenvolvimento e produção

O deploy não substitui o ambiente local.

```text
DESENVOLVIMENTO                    PRODUÇÃO

VS Code                            Render
   ↓                                  ↓
Flask                              Gunicorn
   ↓                                  ↓
SQLite                             PostgreSQL
   ↓                                  ↓
instance/                          Supabase
```

Os dois ambientes utilizam o mesmo código, mas seus bancos de dados são independentes.
