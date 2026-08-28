# Como iniciar o AgiProz

## Windows 10/11

1. Instale o Python 3.12.
2. Abra o terminal na pasta do projeto.
3. Crie o ambiente virtual:

```bash
python -m venv .venv
```

4. Ative o ambiente virtual.
5. Instale as dependências:

```bash
pip install -r requirements.txt
```

6. Execute:

```bash
python app.py
```

7. Abra `http://127.0.0.1:5500` no navegador.

Sem `DATABASE_URL`, o sistema usa SQLite local.
