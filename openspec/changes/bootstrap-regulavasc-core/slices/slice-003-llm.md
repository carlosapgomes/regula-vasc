# Slice 003 — LLM (Prompt Templates)

## Handoff

Leia: `proposal.md`, `design.md`, `tasks.md`, `specs/llm/spec.md`.  
Referência: `../../ats-web/apps/llm/models.py` (PromptTemplate), `../../ats-web/apps/llm/management/commands/seed_prompts.py`.  
Prompts fonte: `../../matrix-pdf-summarizer-bot/prompts/medical_triage.txt` e variantes.

**Estado atual:** Apps accounts (S01) e cases (S02) funcionais. Nenhum gerenciamento de prompts.

## Objetivo

Criar app `llm` com modelo `PromptTemplate` versionado e seed de prompts vasculares adaptados do bot Matrix.

## Escopo funcional

**R1:** Modelo `PromptTemplate` com name, content, version, is_active, created_at, updated_at  
**R2:** Método `PromptTemplate.get_active(name)` retornando template ativo ou None  
**R3:** Seed de 4 prompts (llm1_system, llm1_user, llm2_system, llm2_user) adaptados do bot  
**R4:** Fallback hardcoded no pipeline se template não existir  
**R5:** Tests

## Arquivos esperados

```
apps/llm/
├── __init__.py, apps.py, admin.py
├── models.py
├── migrations/0001_initial.py
├── management/commands/seed_prompts.py
└── tests/test_models.py, test_seed_prompts.py
```

## TDD

**RED:** `test_get_active_returns_none_when_empty`, `test_get_active_returns_active_template`, `test_seed_creates_four_templates`

**GREEN:** Models → seed command → admin

## Checks

```bash
rg -n "get_active\|is_active\|version" apps/llm/models.py
rg -n "llm1_system\|llm1_user\|llm2_system\|llm2_user" apps/llm/management/commands/seed_prompts.py
```

---

Relatório: `/tmp/bootstrap-regulavasc-core-slice-003-report.md`
