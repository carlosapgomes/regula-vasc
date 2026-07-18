# Slice 002 — Cases (Modelo Case + FSM + Lock + Auditoria)

## Handoff para implementador LLM (contexto zero)

Leia: `proposal.md`, `design.md`, `tasks.md`, `specs/cases/spec.md`.  
Referência: `../../ats-web/apps/cases/models.py` (Case FSM, CaseEvent, CaseAttachment, CaseCommunicationMessage), `../../ats-web/apps/cases/services.py` (lock system, administrative closure).

**Estado atual:** App accounts funcional (S01). Usuários e roles existem. Nenhum modelo de domínio.

## Objetivo

Criar o app `cases` com o modelo `Case` (FSM 10 estados), `CaseEvent` (auditoria append-only), `CaseAttachment` (anexos), `CaseCommunicationMessage` (thread), sistema de lock, e serviço de encerramento administrativo.

## Escopo funcional

**R1:** Modelo `Case` com UUID PK, todos os campos do design (pdf_file, extracted_text, structured_data, llm1_primary_result, llm1_secondary_result, llm2_primary_result, llm2_secondary_result, suggested_action, doctor_decision, doctor_reason, doctor_observation, doctor_decided_at, nurse_ack_at, nurse_ack_by, lock fields, administrative closure fields, regulation_days_on_screen, agency_record_number)  
**R2:** FSM com 10 estados e transições: NEW→EXTRACTING→LLM1_STRUCT→LLM2_SUGGEST→WAIT_DOCTOR→DOCTOR_ACCEPTED/DOCTOR_DENIED→WAIT_NURSE_ACK→CLEANED (FAILED a partir de EXTRACTING/LLM1_STRUCT/LLM2_SUGGEST; CLEANED a partir de qualquer estado via administratively_close)  
**R3:** `CaseEvent`: modelo append-only; criado via signal `post_save` quando `case._pending_event` existe; campos: case, timestamp, actor_type, actor, event_type, payload  
**R4:** `CaseAttachment`: anexos com content_type validation (PDF, JPEG, PNG), sha256, upload_phase (initial/supplemental), suppression fields  
**R5:** `CaseCommunicationMessage`: modelo append-only com message_type (user), author, author_role, body, created_at  
**R6:** Lock system: serviços `claim_case_lock`, `assert_case_lock`, `renew_case_lock`, `release_case_lock`, `expire_stale_locks_for_statuses`  
**R7:** `administratively_close_case` service com validação de estado e registro de evento  
**R8:** Tests cobrindo todas as transições FSM, lock, auditoria, anexos, comunicação

## Arquivos esperados

```
apps/cases/
├── __init__.py, apps.py, admin.py
├── models.py        # Case, CaseEvent, CaseAttachment, CaseCommunicationMessage
├── services.py      # lock system, administratively_close_case, post_case_communication_message
├── signals.py       # post_save → create CaseEvent from _pending_event
├── navigation.py    # resolve_safe_next_url
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── test_fsm.py
    ├── test_models.py
    ├── test_lock_service.py
    └── test_administrative_closure.py
```

Modificar: `config/settings/base.py` (INSTALLED_APPS)

## TDD obrigatório

### RED (testes que devem falhar primeiro)
- `test_fsm.py`: testar cada transição (start_extraction, extraction_complete, llm1_complete, llm2_complete, doctor_decide, ready_for_nurse, nurse_ack, administratively_close); testar transições inválidas disparam exceção
- `test_models.py`: testar campos, propriedades (patient_name, patient_age, doctor_display), validações
- `test_lock_service.py`: claim (sucesso, já lockado, status errado), assert (válido, token errado, expirado), renew, release, expire_stale
- `test_administrative_closure.py`: fechar de WAIT_DOCTOR, não fechar CLEANED, evento registrado

### GREEN
Implementar models → signals → services → admin

### REFACTOR
- DRY: extrair helper `_build_lock_result` no serviço de lock
- Garantir que `CaseEvent` é sempre criado via signal, nunca diretamente

## Checks de inspeção

```bash
rg -n "FSMField\|@transition" apps/cases/models.py
rg -n "_record_event\|_pending_event" apps/cases/models.py
rg -n "post_save\|create_case_event" apps/cases/signals.py
rg -n "claim_case_lock\|assert_case_lock" apps/cases/services.py
rg -n "administratively_close_case" apps/cases/services.py
rg -n "CASE_ADMINISTRATIVELY_CLOSED" apps/cases/
```

## Critérios de sucesso

- [ ] 10 estados FSM definidos e testados
- [ ] Todas as transições felizes e de erro funcionam
- [ ] CaseEvent criado automaticamente em cada transição
- [ ] Lock system funcional com timeout
- [ ] Administrative closure registra evento com payload
- [ ] Todos os testes passam

---

**Implement ONLY this slice.** Siga o protocolo. Não crie views/urls/templates ainda. Relatório em `/tmp/bootstrap-regulavasc-core-slice-002-report.md`.
