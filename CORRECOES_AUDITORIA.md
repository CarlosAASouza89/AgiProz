# AgiProz — Correções da Auditoria Técnica

Esta versão incorpora as correções prioritárias identificadas na auditoria técnica.

## Correções aplicadas

1. **Troca obrigatória da senha temporária no backend**
   - Usuários com `force_password_change` não conseguem acessar as demais APIs autenticadas antes de trocar a senha.
   - A rota `/api/password/change` continua liberada para concluir o primeiro acesso.
   - O frontend não tenta carregar `/api/data` antes da troca.

2. **Histórico de pagamentos**
   - O histórico agora apresenta o valor efetivamente registrado no pagamento (`payment.value`), incluindo juros de atraso quando aplicáveis.
   - A data exibida vem do registro do pagamento.

3. **WhatsApp e próxima parcela**
   - As ações de WhatsApp usam a próxima parcela em aberto, em vez do vencimento antigo armazenado no contrato.
   - Para parcelas atrasadas, a mensagem usa o valor atualizado (`amountDue`) quando disponível.

4. **Fuso horário do Brasil**
   - As regras de data/hora do backend usam `America/Sao_Paulo`.
   - O frontend também calcula a data atual no fuso `America/Sao_Paulo`.
   - Isso evita divergências de vencimento e atraso próximas à meia-noite.

5. **Proteção contra múltiplos administradores**
   - SQLite e PostgreSQL recebem um índice único parcial que permite somente um usuário com `role='admin'`.
   - O setup local usa transação imediata para reduzir concorrência durante a criação inicial.

6. **Validação no backend**
   - Nome, login, e-mail corporativo, e-mail de cliente e telefone passam por validação no servidor.
   - A confirmação de WhatsApp agora é obrigatória também na API.
   - As regras não dependem apenas do JavaScript do navegador.

7. **Consistência da recuperação de senha**
   - A interface informa corretamente que `instance/admin_recovery_code.txt` existe apenas no ambiente local.
   - No Render/Supabase, a chave exibida deve ser armazenada pelo administrador em local seguro.

8. **Limpeza adicional**
   - Removida uma exclusão duplicada de cliente encontrada durante a auditoria.
   - Documentação e metadados foram ajustados para não descrever o sistema como somente SQLite.

## Verificações realizadas

- `app.py`: compilação Python OK.
- `db_adapter.py`: compilação Python OK.
- `tests/test_api.py`: compilação Python OK.
- `app.js`: `node --check` OK.
- Os testes Python foram ampliados para cobrir senha temporária, validação de operador e confirmação de WhatsApp.

> A execução da suíte Python depende das dependências do `requirements.txt`. No ambiente de análise atual, Flask não está instalado e não há acesso externo para instalá-lo; por isso a execução completa dos testes deve ser feita no ambiente local ou no GitHub Actions.
