# Slice 005 — Intake (Enfermeiro: Upload e Acompanhamento)

## Handoff

Leia: `proposal.md`, `design.md` (D8), `tasks.md`, `specs/intake/spec.md`.  
Referências: `../../ats-web/apps/intake/` (views.py, forms.py, services.py, urls.py, templates/intake/*), `../../ats-web/apps/intake/pdf_utils.py`.

**Estado atual:** Apps accounts (S01), cases (S02), llm (S03), pipeline (S04) funcionais. Pipeline enfileirável via django-q2. Nenhuma interface de upload.

## Objetivo

Criar o app `intake` com: formulário de upload de PDF + anexos, lista "Meus Casos" com filtros/busca, detalhe do caso com timeline/stepper/PDF viewer, confirmação de ciência, supressão/adição de anexos, e template `case_detail.html` compartilhável.

## Escopo funcional

**R1:** `intake_home`: GET mostra form de upload + casos recentes; POST processa upload, cria Cases, enfileira pipeline  
**R2:** `my_cases`: lista todos casos operacionais (não CLEANED) com filtro por status e busca por agency_record_number  
**R3:** `case_detail`: stepper, timeline de eventos, PDF viewer inline, dados estruturados, resultado final, ações (ciência, anexos, comunicação)  
**R4:** `confirm_receipt`: POST com lock → transição WAIT_NURSE_ACK → CLEANED  
**R5:** `serve_pdf`, `serve_attachment`: FileResponse protegido (cache-control: no-store)  
**R6:** `suppress_attachment`: POST com motivo obrigatório  
**R7:** `add_supplemental_attachment`: POST com justificativa obrigatória, validação de tipo/tamanho  
**R8:** `post_case_communication`: POST com body → cria CaseCommunicationMessage  
**R9:** Status labels, CSS classes, event labels, steps constantes (como no ats-web)  
**R10:** Template `case_detail.html` parametrizado para ser reutilizado por doctor e dashboard

## Arquivos esperados

```
apps/intake/
├── __init__.py, apps.py
├── forms.py           # CaseUploadForm
├── services.py        # process_uploaded_files, validate_attachment_file
├── views.py           # intake_home, my_cases, case_detail, confirm_receipt, serve_pdf, serve_attachment, suppress_attachment, add_supplemental_attachment, post_case_communication, lock renew/release
├── urls.py
└── tests/
    ├── conftest.py
    ├── test_upload.py
    ├── test_my_cases.py
    ├── test_case_detail.py
    ├── test_nir_receipt.py
    └── test_attachment_suppression.py
templates/intake/
├── intake_home.html
├── my_cases.html
├── _my_cases_content.html
├── case_detail.html      # template compartilhado
└── _nav.html
static/js/
├── upload.js
└── work_lock.js
```

Modificar: `config/urls.py` (incluir intake.urls), `config/settings/base.py` (INSTALLED_APPS, MEDIA_ROOT, INTAKE_MAX_ATTACHMENTS_PER_CASE)

## TDD

**RED:**
- `test_upload_creates_case_and_enqueues`: POST com PDF → Case criado, pipeline enfileirado
- `test_upload_rejects_invalid_file`: POST com .docx → erro
- `test_my_cases_shows_all_non_cleaned`: criar 3 casos → listagem mostra 3
- `test_case_detail_shows_timeline`: verificar que eventos aparecem na página
- `test_confirm_receipt_transitions_to_cleaned`: POST com lock → status CLEANED
- `test_confirm_receipt_without_lock_fails`: POST sem token → warning
- `test_suppress_attachment_requires_reason`: POST sem motivo → erro
- `test_add_supplemental_attachment_success`: POST com JPEG + justificativa → CaseAttachment criado

## Checks

```bash
rg -n "STATUS_LABELS\|STATUS_CSS_CLASS\|EVENT_LABELS\|STEPS" apps/intake/views.py
rg -n "confirm_receipt\|WAIT_NURSE_ACK" apps/intake/views.py
rg -n "can_confirm_receipt\|show_intake_nav\|show_doctor_nav\|show_dashboard_nav" templates/intake/case_detail.html
rg -n "process_uploaded_files\|enqueue_pipeline" apps/intake/services.py apps/intake/views.py
```

## Critérios

- [ ] Upload de PDF cria Case e pipeline dispara
- [ ] Lista de casos mostra cards com status e dados do paciente
- [ ] Detalhe do caso mostra stepper, timeline, PDF
- [ ] Ciência do enfermeiro conclui caso
- [ ] Anexos complementares funcionam
- [ ] Supressão de anexos registra evento
- [ ] Template case_detail.html é parametrizável para outros papéis

---

Relatório: `/tmp/bootstrap-regulavasc-core-slice-005-report.md`
