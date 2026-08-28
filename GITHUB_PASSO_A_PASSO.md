# Publicação no GitHub

Este documento apresenta um fluxo simples para versionar o AgiProz no GitHub e prepará-lo para integração com o Render.

## 1. Verificação antes do primeiro envio

Antes de executar `git add .`, confirme que não existem credenciais ou dados locais que devam ser publicados.

Não devem ser enviados:

- `.env`;
- `instance/`;
- `*.sqlite3`;
- `*.sqlite`;
- senhas;
- `DATABASE_URL` com credenciais;
- chaves secretas;
- chaves de recuperação;
- arquivos temporários.

O projeto possui `.gitignore` configurado para ignorar esses arquivos.

## 2. Inicializar o repositório

Na pasta do projeto:

```bash
git init
git status
```

Confira a lista apresentada pelo Git antes de continuar.

## 3. Fazer o primeiro commit

```bash
git add .
git status
git commit -m "Versão inicial do AgiProz"
```

## 4. Conferir arquivos ignorados

Para verificar se o banco local está sendo ignorado:

```bash
git check-ignore -v instance/agiproz.sqlite3
```

O comando deve indicar a regra do `.gitignore` responsável por ignorar o arquivo.

Também é recomendável revisar:

```bash
git status
git diff
```

## 5. Criar e conectar o repositório remoto

No GitHub, crie um repositório para o projeto. Depois, no terminal:

```bash
git branch -M main
git remote add origin URL_DO_REPOSITORIO
git push -u origin main
```

Substitua `URL_DO_REPOSITORIO` pelo endereço do seu repositório.

## 6. Organização das alterações

Para uma equipe acadêmica, use branches por tarefa:

```text
main
├── feature/clientes
├── feature/emprestimos
├── feature/pagamentos
└── feature/interface
```

Cada integrante deve trabalhar na própria branch e abrir um Pull Request para `main` quando a alteração estiver pronta para revisão.

## 7. Fluxo recomendado

```text
Alteração no VS Code
        ↓
       Git
        ↓
     Branch
        ↓
     Commit
        ↓
     GitHub
        ↓
 Pull Request
        ↓
    Revisão
        ↓
      main
        ↓
     Render
```

A branch `main` deve representar uma versão estável do projeto.

## 8. Relação com o banco de dados

O código publicado no GitHub não deve conter o banco SQLite local nem as credenciais do PostgreSQL.

No ambiente hospedado, o Render recebe a `DATABASE_URL` por variável de ambiente e a aplicação utiliza PostgreSQL no Supabase.

```text
GitHub
   │
   │ código
   ▼
Render
   │
   │ DATABASE_URL
   ▼
Supabase PostgreSQL
```

A `DATABASE_URL` não deve ser escrita em arquivos versionados.

## 9. Integração com o Render

O repositório GitHub funciona como origem do código utilizado pelo Render.

Após uma alteração ser enviada para a branch configurada no serviço, o Render pode realizar um novo deploy conforme a configuração do serviço.

## 10. Comandos úteis

Verificar o estado:

```bash
git status
```

Verificar alterações:

```bash
git diff
```

Listar branches:

```bash
git branch
```

Enviar uma branch:

```bash
git push -u origin NOME_DA_BRANCH
```

## 11. Regra principal de segurança

O GitHub deve armazenar o código e a documentação do projeto, não as credenciais nem os dados privados dos ambientes de execução.
