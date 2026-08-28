# Casos de teste

## Autenticação

- Primeiro acesso sem administrador deve solicitar a criação do administrador.
- Login com credenciais válidas deve permitir acesso.
- Login com senha incorreta deve ser recusado.
- Usuário desativado não pode iniciar sessão.
- Senha temporária deve exigir troca no primeiro acesso.

## Usuários

- Somente o administrador pode criar operadores.
- Somente o administrador pode editar, ativar, desativar ou redefinir operadores.
- A senha temporária deve ser gerada pelo servidor.

## Clientes

- CPF inválido deve ser recusado.
- CPF, e-mail e telefone duplicados devem ser recusados.
- Cliente com empréstimo não pode ser excluído.

## Empréstimos

- Valor deve respeitar os limites definidos pelo projeto.
- A taxa deve estar entre 0% e 100%.
- O número de parcelas deve estar entre 1 e 36.
- Periodicidade semanal deve avançar 7 dias.
- Periodicidade quinzenal deve avançar 14 dias.
- Periodicidade mensal deve preservar o dia de referência quando possível.
- Um contrato iniciado em 31/01 deve gerar 28/02, 31/03 e 30/04.

## Pagamentos

- A primeira parcela pendente deve ser paga antes das seguintes.
- Uma parcela paga não pode receber outro pagamento.
- Pagamento em atraso deve aplicar a regra acadêmica de juros.
- O valor devolvido pela API deve ser o valor efetivamente registrado.
- Somente o último pagamento do contrato pode ser desfeito.
- O desfazimento deve reabrir a parcela e o contrato.

## Auditoria

- Acesso à auditoria deve ser exclusivo do administrador.
- Operações relevantes devem gerar registros de auditoria.

## Publicação

- O projeto deve iniciar sem `DATABASE_URL` usando SQLite.
- Com `DATABASE_URL`, deve utilizar PostgreSQL.
- O Render deve iniciar com Gunicorn e responder ao health check.
