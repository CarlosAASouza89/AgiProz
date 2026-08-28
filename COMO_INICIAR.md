# Como iniciar o AgiProz

Este documento descreve a execução do AgiProz em ambiente local pelo VS Code.

## Requisitos

- Windows 10/11;
- Python 3.12;
- VS Code;
- navegador web atualizado.

## 1. Abrir o projeto no VS Code

1. Abra o VS Code.
2. Selecione `Arquivo → Abrir Pasta`.
3. Escolha a pasta `AgiProz`.
4. Abra `Terminal → Novo Terminal`.

Todos os comandos abaixo devem ser executados dentro da pasta do projeto.

## 2. Criar o ambiente virtual

```bash
python -m venv .venv
```

O ambiente virtual mantém as dependências do projeto separadas das demais instalações do Python.

## 3. Ativar o ambiente virtual

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### Windows CMD

```cmd
.venv\Scripts\activate.bat
```

Quando o ambiente estiver ativo, o terminal normalmente exibirá `.venv` no início da linha.

## 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

## 5. Escolher o banco de dados

A aplicação utiliza `DATABASE_URL` para determinar o banco.

```text
DATABASE_URL não definida
        ↓
SQLite local
        ↓
instance/agiproz.sqlite3
```

```text
DATABASE_URL definida
        ↓
PostgreSQL
        ↓
Supabase
```

### Execução local padrão

Para desenvolver e testar localmente com SQLite, não é necessário configurar `DATABASE_URL`.

### Execução local com PostgreSQL

Também é possível executar a aplicação pelo VS Code utilizando o PostgreSQL do Supabase. Nesse caso, configure `DATABASE_URL` no ambiente antes de iniciar a aplicação.

A conexão deve ser mantida em variável de ambiente e nunca deve ser colocada diretamente no código ou publicada no GitHub.

## 6. Iniciar a aplicação

```bash
python app.py
```

A aplicação será disponibilizada em:

```text
http://127.0.0.1:5500
```

Abra esse endereço no navegador.

## 7. Primeiro acesso

Na primeira execução, o banco estará sem usuários. Utilize a tela inicial para criar o administrador conforme as regras de senha apresentadas pela aplicação.

No modo SQLite, os dados locais serão armazenados em:

```text
instance/agiproz.sqlite3
```

A pasta `instance/` não deve ser enviada ao GitHub.

## 8. Executar os testes

Com o ambiente virtual ativo:

```bash
python -m unittest discover -s tests -v
```

Os testes verificam os principais fluxos da aplicação sem depender do banco de produção.

## 9. Encerrar a execução

No terminal em que o Flask estiver rodando, pressione:

```text
Ctrl + C
```

Para sair do ambiente virtual:

```bash
deactivate
```

## Observação sobre os ambientes

A execução local e a execução hospedada utilizam a mesma aplicação, mas normalmente trabalham com bancos diferentes:

```text
LOCAL                         HOSPEDADO
VS Code                       Render
  ↓                             ↓
Flask                         Gunicorn
  ↓                             ↓
SQLite                        PostgreSQL
  ↓                             ↓
instance/                     Supabase
```

Os dados dos dois ambientes não são sincronizados automaticamente.
