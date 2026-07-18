# Slice 007 — Dashboard (Admin: Métricas e Gestão)

## Handoff

Leia: `proposal.md`, `design.md` (D9), `tasks.md`, `specs/dashboard/spec.md`.  
Referências: `../../ats-web/apps/dashboard/` (views.py, templates/dashboard/*, templatetags/), `../../ats-web/apps/admin_ui/` (user/prompt management).

**Estado atual:** Doctor (S06) funcional. Casos fluem por todo o pipeline. Nenhuma interface administrativa.

## Objetivo

Criar app `dashboard` com métricas de fluxo, tabela de todos os casos (filtrável, paginada, com busca), encerramento administrativo, gestão de usuários (CRUD), gestão de prompts e configuração dos providers LLM.

## Escopo funcional

**R1:** `dashboard_index`: cards de métricas (total, aceitos, recusados, admin closed, pendentes, aguardando médico, aguardando enfermeiro) filtráveis por período (hoje, 7d, 30d, all)  
**R2:** Tempos médios: upload→decisão médica, decisão→ciência, ciclo total  
**R3:** Tabela de casos paginada (20/página) com filtros (status, data) e busca server-side (nome, agency_record_number, min 3 chars)  
**R4:** Cards de atenção: casos FAILED, processamento parado >30min, espera humana >48h  
**R5:** `dashboard_case_detail`: detalhe de qualquer caso (reutiliza template compartilhado) + botão encerrar administrativamente  
**R6:** `administrative_close`: POST com reason_code (predefined choices) + reason_text  
**R7:** `dashboard_user_list` / `user_create` / `user_edit`: CRUD de usuários com assign de roles  
**R8:** `dashboard_prompt_list` / `prompt_create`: gestão de prompts (criar nova versão, ativar)  
**R9:** Configuração de LLM providers: editar primary/secondary provider, model, api_key, enable/disable secondary

## Arquivos esperados

```
apps/dashboard/
├── __init__.py, apps.py
├── views.py           # dashboard_index, dashboard_case_detail, administratively_close, user CRUD, prompt CRUD, llm_config
├── urls.py
├── templatetags/
│   ├── __init__.py
│   └── dashboard_extras.py
└── tests/
    ├── __init__.py
    ├── test_dashboard.py
    └── test_administrative_closure.py
templates/dashboard/
├── index.html
├── _case_list.html
├── _nav.html
├── user_list.html
├── user_form.html
├── prompt_list.html
└── prompt_create.html
static/js/
└── dashboard_search.js
```

Modificar: `config/urls.py`, `config/settings/base.py`

## TDD

**RED:**
- `test_dashboard_metrics_count`: criar casos com diferentes outcomes → métricas batem
- `test_dashboard_avg_times`: criar casos com timestamps → tempos calculados corretamente
- `test_dashboard_search_by_patient_name`: criar caso com nome → busca retorna
- `test_dashboard_search_min_3_chars`: busca com 1 char → não filtra
- `test_administrative_close_from_wait_doctor`: POST → CLEANED, evento registrado
- `test_administrative_close_cleaned_rejected`: tentar fechar CLEANED → erro
- `test_admin_can_create_user`: POST user form → User criado com roles
- `test_admin_can_activate_prompt`: criar nova versão → `get_active` retorna nova

## Checks

```bash
rg -n "administratively_close\|CASE_ADMINISTRATIVELY_CLOSED" apps/dashboard/views.py
rg -n "attention\|ATTENTION_PROCESSING\|ATTENTION_WAITING" apps/dashboard/views.py
rg -n "search\|lower.*contains\|trigram" apps/dashboard/views.py
rg -n "@role_required.*admin\|@role_required.*manager" apps/dashboard/views.py
rg -n "LLM_SECONDARY_ENABLED\|LLM1_PRIMARY\|LLM2_PRIMARY" apps/dashboard/views.py templates/dashboard/
```

## Critérios

- [ ] Métricas diárias e por período funcionam
- [ ] Tabela de casos com paginação, filtros e busca
- [ ] Encerramento administrativo funcional de qualquer estado
- [ ] CRUD de usuários funcional
- [ ] Gestão de prompts funcional
- [ ] Configuração de LLM providers funcional
- [ ] Cards de atenção identificam casos problemáticos

---

Relatório: `/tmp/bootstrap-regulavasc-core-slice-007-report.md`
