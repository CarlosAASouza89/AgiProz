# Guia do código — AgiProz

O projeto possui uma estrutura simples para facilitar a apresentação e o estudo.

## Arquivos principais

- `app.py`: aplicação Flask, autenticação, regras de negócio e rotas da API.
- `db_adapter.py`: conexão com SQLite e PostgreSQL.
- `index.html`: estrutura das telas e formulários.
- `style.css`: layout e identidade visual.
- `app.js`: interação da interface e comunicação com a API.
- `assets/`: imagens utilizadas pela interface.
- `tests/test_api.py`: testes automatizados da API.

## Ordem sugerida para estudo

1. Leia `index.html` para identificar as telas e os formulários.
2. Leia `style.css` para entender o layout e os componentes visuais.
3. Comece `app.js` pelas funções de comunicação com a API e autenticação.
4. Leia `app.py` começando por configuração, banco, autenticação e autorização.
5. Depois acompanhe clientes, empréstimos, parcelas, pagamentos e mensagens.
6. Por fim, leia `tests/test_api.py` para ver como os principais fluxos são validados.

## Banco de dados

Sem `DATABASE_URL`, o sistema utiliza SQLite. Com `DATABASE_URL`, utiliza PostgreSQL.

Essa escolha permite apresentar o projeto localmente e, ao mesmo tempo, publicá-lo no Render usando Supabase.

## Observação acadêmica

As regras financeiras são simplificadas para fins didáticos. O projeto não foi desenvolvido para operar como instituição financeira real.
