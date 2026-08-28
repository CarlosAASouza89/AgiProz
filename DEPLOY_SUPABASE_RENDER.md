# Deploy do AgiProz com GitHub, Supabase e Render

A arquitetura usada no deploy é:

```text
GitHub → Render → Supabase PostgreSQL
```

## 1. Criar o banco no Supabase

1. Crie um projeto no Supabase.
2. Abra a área de conexão do banco.
3. Copie uma URL PostgreSQL destinada a aplicações de servidor.
4. Mantenha a URL em segredo.
5. Se a URL fornecida pelo Supabase não trouxer SSL, utilize uma configuração com `sslmode=require`.

O AgiProz cria as tabelas automaticamente na primeira conexão.

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

O projeto já possui `render.yaml`. Ao usar o Blueprint, o Render utilizará:

- Python;
- `pip install -r requirements.txt` no build;
- Gunicorn no start;
- `/api/bootstrap` como health check.

Configure as variáveis:

```text
DATABASE_URL = URL PostgreSQL do Supabase
AGIPROZ_SECRET_KEY = chave longa e aleatória
SESSION_COOKIE_SECURE = 1
```

O `render.yaml` já gera automaticamente uma `AGIPROZ_SECRET_KEY` quando o serviço é criado por Blueprint.

## 4. Primeiro acesso no Render

Depois do deploy, abra a URL fornecida pelo Render e crie o administrador.

A chave de recuperação deve ser copiada e guardada em local seguro. Em PostgreSQL o sistema não depende de arquivo local para manter a chave; somente o hash é armazenado no banco.

## 5. Trabalho acadêmico em equipe

Recomenda-se que cada integrante trabalhe em uma branch própria:

```text
main
└── feature/nome-da-tarefa
```

Depois, abra um Pull Request para revisão antes de juntar a alteração à `main`.

## 6. Cuidados antes de publicar

Nunca coloque no repositório:

- `.env`;
- `DATABASE_URL`;
- senhas;
- banco SQLite com dados pessoais;
- chave de recuperação;
- arquivos da pasta `instance/`.
