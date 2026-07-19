# Tasks: Bootstrap RegulaVasc Core

## 1. S00 — Bootstrap do Projeto

- [x] 1.1 Criar estrutura Django: `config/`, `apps/`, `templates/`, `static/`, `manage.py`
- [x] 1.2 Criar `pyproject.toml` com dependências (django, django-q2, pymupdf, openai, pydantic, etc.)
- [x] 1.3 Criar `config/settings/base.py`, `dev.py`, `test.py`
- [x] 1.4 Criar `docker-compose.yml` com PostgreSQL 17 + app
- [x] 1.5 Criar `templates/base.html` com tema hospitalar, PWA meta tags, navbar Bootstrap 5.3
- [x] 1.6 Criar `static/css/app.css` com variáveis CSS e tema hospitalar
- [x] 1.7 Criar `static/manifest.json` e `static/js/sw.js` (service worker)
- [x] 1.8 Criar `conftest.py` com fixtures base pytest-django
- [x] 1.9 Criar `templates/home.html` (landing page inicial)
- [x] 1.10 Criar `config/urls.py` root URLconf

Ver slice: `slices/slice-000-bootstrap.md`

## 2. S01 — Accounts (Autenticação e Papéis)

- [x] 2.1 Criar app `apps/accounts/` com modelos User (AbstractUser), Role, ProfessionalCouncil
- [x] 2.2 Criar migration inicial + seed de roles (nurse, doctor, admin)
- [x] 2.3 Criar views: login, logout, switch_role, profile, password_change, password_reset
- [x] 2.4 Criar templates: login.html, profile.html, switch_role.html, password_reset*.html
- [x] 2.5 Criar `@role_required` decorator e context processor de `active_role`
- [x] 2.6 Criar comando `seed_admin` para criar admin inicial
- [x] 2.7 Criar email backend para password reset (console em dev, SMTP em prod)
- [x] 2.8 Testes: models, views, decorators, password reset flow

Ver slice: `slices/slice-001-accounts.md`

## 3. S02 — Cases (Modelo Case + FSM)

- [x] 3.1 Criar app `apps/cases/` com modelos Case, CaseEvent, CaseAttachment, CaseCommunicationMessage
- [x] 3.2 Implementar FSM com 10 estados e transições (django-fsm)
- [x] 3.3 Implementar CaseEvent (auditoria append-only) e signal para criar eventos pós-save
- [x] 3.4 Implementar CaseAttachment com upload_to, supressão, e validação de content_type
- [x] 3.5 Implementar CaseCommunicationMessage (thread operacional)
- [x] 3.6 Implementar lock system: claim, assert, renew, release, expire_stale
- [x] 3.7 Implementar `administratively_close_case` service
- [x] 3.8 Criar admin.py para Case e CaseEvent
- [x] 3.9 Testes: FSM transitions, modelos, lock system, CaseEvent creation, administrative closure

Ver slice: `slices/slice-002-cases.md`

## 4. S03 — LLM (Prompt Templates)

- [ ] 4.1 Criar app `apps/llm/` com modelo PromptTemplate (versionado, com get_active)
- [ ] 4.2 Criar migration inicial
- [ ] 4.3 Criar comando `seed_prompts` com prompts vasculares portados do bot Matrix
- [ ] 4.4 Criar admin.py para PromptTemplate
- [ ] 4.5 Testes: modelo, seed, get_active, versionamento

Ver slice: `slices/slice-003-llm.md`

## 5. S04 — Pipeline (LLM Client + Extração + Orquestração)

- [ ] 5.1 Criar app `apps/pipeline/` com estrutura de diretórios (schemas/, __init__, etc.)
- [ ] 5.2 Criar `apps/pipeline/llm.py` com protocolo LlmClient e implementações multi-provider
- [ ] 5.3 Criar `apps/pipeline/schemas/llm1.py` — schema Pydantic `Llm1VascularResponse`
- [ ] 5.4 Criar `apps/pipeline/schemas/llm2.py` — schema Pydantic `Llm2VascularResponse`
- [ ] 5.5 Criar `apps/pipeline/llm1_service.py` — serviço de extração estruturada
- [ ] 5.6 Criar `apps/pipeline/llm2_service.py` — serviço de parecer/sugestão
- [ ] 5.7 Criar `apps/pipeline/orchestrator.py` — orquestrador do pipeline completo (com dual-LLM)
- [ ] 5.8 Criar `apps/pipeline/json_parser.py` — parser JSON robusto com fallback
- [ ] 5.9 Criar `apps/pipeline/tasks.py` — entry points django-q2
- [ ] 5.10 Criar `apps/pipeline/pdf_utils.py` — extração de texto (pymupdf), watermark removal, extração de agency_record_number e regulation_days_on_screen
- [ ] 5.11 Testes: LLM client mock, LLM1 service, LLM2 service, orchestrator, JSON parser, dual-LLM (ambos sucesso, falha de um), schemas Pydantic validation

Ver slice: `slices/slice-004-pipeline.md`

## 6. S05 — Intake (Enfermeiro: Upload e Acompanhamento)

- [ ] 6.1 Criar app `apps/intake/` com estrutura
- [ ] 6.2 Criar `intake/forms.py` — CaseUploadForm com validação de PDF e anexos
- [ ] 6.3 Criar `intake/services.py` — `process_uploaded_files`, `validate_attachment_file`
- [ ] 6.4 Criar views: `intake_home` (upload), `my_cases` (lista), `case_detail` (detalhe + timeline)
- [ ] 6.5 Criar view: `confirm_receipt` (ciência do enfermeiro)
- [ ] 6.6 Criar views: `serve_pdf`, `serve_attachment` (protegidas)
- [ ] 6.7 Criar views: `suppress_attachment`, `add_supplemental_attachment`
- [ ] 6.8 Criar view: `post_case_communication` (mensagem na thread)
- [ ] 6.9 Criar templates: `intake_home.html`, `my_cases.html`, `case_detail.html` (compartilhado)
- [ ] 6.10 Criar partials: `_my_cases_content.html` (HTMX polling)
- [ ] 6.11 Criar `intake/urls.py`
- [ ] 6.12 Testes: upload (PDF válido, inválido, múltiplos), my_cases, case_detail, confirm_receipt, lock flow, comunicação, anexos

Ver slice: `slices/slice-005-intake.md`

## 7. S06 — Doctor (Médico: Fila e Decisão)

- [ ] 7.1 Criar app `apps/doctor/` com estrutura
- [ ] 7.2 Criar `doctor/forms.py` — DoctorDecisionForm (accept/deny, reason, observation)
- [ ] 7.3 Criar `doctor/presenters.py` — presenter de relatório vascular formatado
- [ ] 7.4 Criar views: `doctor_queue` (fila pendente + decididos hoje)
- [ ] 7.5 Criar views: `doctor_decision` (GET: formulário) e `doctor_submit` (POST: processar)
- [ ] 7.6 Criar views: `serve_pdf`, `serve_attachment` (protegidas para doctor)
- [ ] 7.7 Criar views: lock renew/release (heartbeat)
- [ ] 7.8 Criar templates: `queue.html`, `decision.html` (com dual-LLM display)
- [ ] 7.9 Criar partials: `_queue_content.html`
- [ ] 7.10 Criar `doctor/urls.py`
- [ ] 7.11 Testes: queue (pendente, decididos), decision (accept, deny sem reason, deny com reason), lock, presenter, dual-LLM display

Ver slice: `slices/slice-006-doctor.md`

## 8. S07 — Dashboard (Admin: Métricas e Gestão)

- [ ] 8.1 Criar app `apps/dashboard/` com estrutura
- [ ] 8.2 Criar `dashboard/views.py` — `dashboard_index` com métricas, tabela de casos, filtros
- [ ] 8.3 Criar `dashboard/views.py` — `dashboard_case_detail` (detalhe + encerramento administrativo)
- [ ] 8.4 Criar `dashboard/views.py` — `dashboard_administrative_close` (POST)
- [ ] 8.5 Criar `dashboard/views.py` — `dashboard_user_list` (CRUD de usuários)
- [ ] 8.6 Criar `dashboard/views.py` — `dashboard_prompt_list` (gestão de prompts)
- [ ] 8.7 Criar `dashboard/views.py` — `dashboard_llm_config` (configuração dos providers LLM)
- [ ] 8.8 Criar templates: `index.html`, `_case_list.html`, `_nav.html`
- [ ] 8.9 Criar `dashboard/urls.py`
- [ ] 8.10 Criar template tags: `dashboard_extras.py` (formatação de duração, etc.)
- [ ] 8.11 Testes: métricas, encerramento administrativo, CRUD de usuários, prompts, busca, filtros

Ver slice: `slices/slice-007-dashboard.md`

## 9. S08 — Comunicação (Thread Operacional)

- [ ] 9.1 Criar partial `_communication_thread.html` reutilizável
- [ ] 9.2 Integrar thread no `case_detail.html` (intake, doctor, dashboard)
- [ ] 9.3 Criar endpoint POST `/cases/<id>/communication/` com redirect seguro
- [ ] 9.4 Implementar validações: autor com papel ativo, corpo não vazio, caso não CLEANED
- [ ] 9.5 Registrar CASE_COMMUNICATION_MESSAGE_POSTED no CaseEvent
- [ ] 9.6 Testes: post válido, post inválido (vazio, CLEANED, sem role), validação de redirect

Ver slice: `slices/slice-008-communication.md`

## 10. S09 — Anexos e Polimento PWA

- [x] 10.1 Criar visualizador de imagens mobile (`mobile_image_viewer.html`)
- [x] 10.2 Criar visualizador PDF mobile com PDF.js (`mobile_pdf_viewer.html`)
- [x] 10.3 Integrar viewers nos fluxos intake, doctor, dashboard
- [x] 10.4 Testar PWA: installabilidade, service worker caching, manifest válido
- [x] 10.5 Criar ícones PWA nos tamanhos corretos
- [x] 10.6 Testes de integração end-to-end dos fluxos principais

Ver slice: `slices/slice-009-polish.md`
