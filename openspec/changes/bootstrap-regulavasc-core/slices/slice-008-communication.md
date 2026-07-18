# Slice 008 — Comunicação (Thread Operacional)

## Handoff

Leia: `proposal.md`, `design.md`, `tasks.md`, `specs/cases/spec.md` (Case Communication Messages).  
Referências: `../../ats-web/templates/cases/_communication_thread.html`, `../../ats-web/apps/cases/services.py` (`post_case_communication_message`), `../../ats-web/apps/intake/views.py` (`post_case_communication`).

**Estado atual:** Modelo CaseCommunicationMessage já existe (S02), mas não há interface para postar ou visualizar mensagens. Templates case_detail.html existem para intake e doctor.

## Objetivo

Criar partial compartilhado de thread de comunicação, integrá-lo nos templates de detalhe do caso (intake, doctor, dashboard), e criar endpoint POST para envio de mensagens com validações.

## Escopo funcional

**R1:** Partial `_communication_thread.html`: exibe mensagens em ordem cronológica com autor, papel, timestamp e corpo  
**R2:** Integrar partial no `case_detail.html` (intake) — visível para enfermeiro  
**R3:** Integrar partial no `decision.html` (doctor) — visível para médico  
**R4:** Integrar partial no caso detalhe do dashboard — read-only para admin  
**R5:** Endpoint POST `/cases/<uuid>/communication/`: valida body não vazio (máx 2000 chars), caso não CLEANED, autor com papel ativo; cria CaseCommunicationMessage + CaseEvent  
**R6:** Redirect seguro após POST (valida `url_has_allowed_host_and_scheme`)  
**R7:** Formulário de post no partial: textarea + botão submit (oculto se caso CLEANED)

## Arquivos esperados

```
templates/cases/
└── _communication_thread.html   # NOVO: partial reutilizável
apps/intake/views.py              # MODIFICAR: adicionar post_case_communication (se não existir)
apps/cases/services.py            # MODIFICAR: adicionar post_case_communication_message (se não existir)
templates/intake/case_detail.html # MODIFICAR: incluir partial + form
templates/doctor/decision.html    # MODIFICAR: incluir partial + form
templates/dashboard/index.html ou case_detail  # MODIFICAR: incluir partial (read-only)
config/urls.py                    # MODIFICAR: adicionar rota se necessário
```

## TDD

**RED:**
- `test_post_communication_message_success`: POST com body válido → 302, mensagem criada
- `test_post_communication_message_empty_body`: POST com body vazio → erro
- `test_post_communication_message_cleaned_case`: POST em caso CLEANED → erro
- `test_post_communication_message_requires_auth`: POST sem login → 302 para login
- `test_communication_thread_appears_on_case_detail`: GET case_detail → partial renderizado com mensagens existentes
- `test_communication_form_hidden_for_cleaned`: GET case_detail CLEANED → textarea não renderizado

## Checks

```bash
rg -n "_communication_thread\|communication_messages" templates/intake/case_detail.html templates/doctor/decision.html
rg -n "post_case_communication_message\|CaseCommunicationError" apps/cases/services.py apps/intake/views.py
rg -n "can_post_communication\|communication_post_url" templates/intake/case_detail.html templates/doctor/decision.html
rg -n "url_has_allowed_host_and_scheme" apps/intake/views.py
```

## Critérios

- [ ] Mensagens aparecem em ordem cronológica nos detalhes (intake, doctor, dashboard)
- [ ] Formulário de post disponível apenas para casos não CLEANED
- [ ] Body vazio ou >2000 chars rejeitado
- [ ] Cada post cria CaseEvent `CASE_COMMUNICATION_MESSAGE_POSTED`
- [ ] Redirect após POST é seguro
- [ ] Thread no dashboard é read-only (sem form)

---

Relatório: `/tmp/bootstrap-regulavasc-core-slice-008-report.md`
