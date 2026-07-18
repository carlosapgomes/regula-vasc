# Slice 006 — Doctor (Médico: Fila e Decisão)

## Handoff

Leia: `proposal.md`, `design.md` (D7), `tasks.md`, `specs/doctor/spec.md`.  
Referências: `../../ats-web/apps/doctor/` (views.py, forms.py, presenters.py, templates/doctor/*), `../../ats-web/apps/cases/services.py` (lock system).

**Estado atual:** Intake (S05) funcional. Casos chegam a WAIT_DOCTOR. Nenhuma interface médica.

## Objetivo

Criar app `doctor` com fila médica, formulário de decisão (aceitar/recusar), presenter de relatório vascular formatado, e visão lado-a-lado dos pareceres dual-LLM.

## Escopo funcional

**R1:** `doctor_queue`: fila WAIT_DOCTOR (ordenada por regulation_days desc, created_at) + aba "Decididos Hoje"  
**R2:** `doctor_decision` GET: formulário com structured data formatado (presenter), dual-LLM cards, PDF viewer, anexos, formulário de decisão; adquire lock  
**R3:** `doctor_decision` POST: valida lock, processa accept/deny, FSM transitions, libera lock  
**R4:** Accept: observation opcional; deny: reason obrigatório  
**R5:** Dual-LLM display: se secundário habilitado → 2 cards lado a lado; se não → 1 card; destaque visual se divergentes  
**R6:** `doctor/presenters.py`: gera HTML formatado com seções: Dados do Paciente, Queixa e Evolução, Lesão, Dor, Pulsos, Antecedentes, Exames, Infecção, Edema  
**R7:** Lock heartbeat (renew) e release explícito  
**R8:** `serve_pdf`, `serve_attachment` protegidos para doctor

## Arquivos esperados

```
apps/doctor/
├── __init__.py, apps.py
├── forms.py           # DoctorDecisionForm
├── views.py           # doctor_queue, doctor_decision, doctor_submit, serve_pdf, serve_attachment, lock renew/release, doctor_decided_detail
├── presenters.py      # prepare_doctor_case_report, build_report (vascular sections)
├── urls.py
└── tests/
    ├── __init__.py
    ├── test_views.py
    ├── test_presenter.py
    └── test_dual_llm_display.py
templates/doctor/
├── queue.html
├── _queue_content.html
├── decision.html
└── _nav.html
static/js/
├── decision.js
├── doctor_queue_filter.js
└── work_lock.js   # (se não criado antes)
```

Modificar: `config/urls.py`, `config/settings/base.py`

## TDD

**RED:**
- `test_queue_shows_wait_doctor_cases`: criar caso WAIT_DOCTOR → aparece na fila
- `test_queue_ordered_by_regulation_days`: casos com dias diferentes → ordem correta
- `test_decision_accept_transitions`: POST accept → DOCTOR_ACCEPTED → WAIT_NURSE_ACK
- `test_decision_deny_requires_reason`: POST deny sem reason → form error
- `test_decision_deny_with_reason_succeeds`: POST deny com reason → DOCTOR_DENIED
- `test_lock_acquired_on_decision_open`: GET → lock adquirido
- `test_second_doctor_blocked`: GET por outro doctor com lock ativo → redirect com warning
- `test_presenter_formats_all_sections`: structured_data completo → HTML contém todas as seções
- `test_dual_llm_both_cards_present`: secondary enabled → 2 cards no template

## Checks

```bash
rg -n "dual.llm\|primary_result\|secondary_result\|LLM_SECONDARY_ENABLED" apps/doctor/views.py templates/doctor/decision.html
rg -n "presenter\|build_report\|prepare_doctor" apps/doctor/presenters.py
rg -n "accept\|deny\|doctor_decision\|doctor_reason" apps/doctor/forms.py apps/doctor/views.py
rg -n "@role_required.*doctor" apps/doctor/views.py
rg -n "regulation_days_on_screen.*desc\|nulls_last" apps/doctor/views.py
```

## Critérios

- [ ] Fila mostra casos WAIT_DOCTOR ordenados por urgência
- [ ] Decisão accept/deny funciona com validações
- [ ] Recusa sem justificativa é rejeitada
- [ ] Presenter gera relatório vascular com todas as seções
- [ ] Dual-LLM cards aparecem lado a lado quando secundário habilitado
- [ ] Lock previne acesso simultâneo ao mesmo caso

---

Relatório: `/tmp/bootstrap-regulavasc-core-slice-006-report.md`
