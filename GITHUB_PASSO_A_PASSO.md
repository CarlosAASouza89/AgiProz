# Publicação no GitHub

## Primeiro envio

Na pasta do projeto:

```bash
git init
git add .
git commit -m "Versão inicial do AgiProz"
git branch -M main
git remote add origin URL_DO_REPOSITORIO
git push -u origin main
```

## Organização das alterações

Para uma equipe acadêmica, use branches por tarefa:

```text
feature/clientes
feature/emprestimos
feature/pagamentos
feature/interface
```

Cada integrante deve enviar sua branch e abrir um Pull Request para `main`.

## Antes de cada envio

Confira:

```bash
git status
git diff
```

O `.gitignore` do projeto já exclui ambiente virtual, arquivos `.env`, `instance/` e bancos locais.
