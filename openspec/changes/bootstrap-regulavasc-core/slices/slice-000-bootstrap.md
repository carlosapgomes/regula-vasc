# Slice 000 — Bootstrap do Projeto

## Handoff para implementador LLM (contexto zero)

Antes de editar, leia:
- `openspec/changes/bootstrap-regulavasc-core/proposal.md`
- `openspec/changes/bootstrap-regulavasc-core/design.md`
- `openspec/changes/bootstrap-regulavasc-core/tasks.md`
- Projeto de referência: `../../ats-web/` (leia `pyproject.toml`, `config/settings/base.py`, `templates/base.html`, `static/css/app.css`, `static/manifest.json`, `conftest.py`)

**Estado atual:** O diretório `regula-vasc/` está vazio (exceto `openspec/` e `.pi/`). Não há código Django ainda.

## Protocolo obrigatório para implementador DeepSeek4-Flash

1. **Plano antes de editar**: escreva no relatório a mini matriz `Requisito → arquivo(s) → teste(s)`.
2. **Baseline de pytest**: `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no estado inicial limpo. Se houver `failed/error`, pare e reporte INCOMPLETE/BLOQUEADO.
3. **RED real**: crie testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado.
4. **GREEN mínimo**: implemente somente o necessário para os testes passarem.
5. **Verificação por inspeção**: execute `rg` checks descritos abaixo.
6. **Quality gate completo**: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest` — exit code 0, zero failures/errors, `passed_final >= passed_baseline`.
7. **Relatório com evidência**: crie `/tmp/bootstrap-regulavasc-core-slice-000-report.md`.

### Condições automáticas de INCOMPLETO

Marque como INCOMPLETO se: teste planejado não executado; baseline não registrado; quality gate não executado; qualquer teste/lint/mypy falhou; `passed_final < passed_baseline`; `tasks.md` foi marcado apesar de falha; relatório não criado no caminho exigido.

## Objetivo

Criar a estrutura base do projeto Django: scaffolding, configurações, dependências, template base com tema hospitalar, PWA manifest e service worker, e landing page inicial. Ao final, `uv run manage.py runserver` deve servir uma página inicial funcional.

## Contexto técnico atual

- Diretório `regula-vasc/` vazio (exceto openspec)
- Stack definida: Python 3.13+, Django 5.2, PostgreSQL 17, Bootstrap 5.3 CDN, uv, pytest, ruff, mypy
- Nome do app Django = `regula_vasc`
- Tema hospitalar: cor primária `#0b4263`, fontes Merriweather Sans + Source Sans 3

## Escopo funcional

**R1:** Projeto Django inicializável com `uv run manage.py runserver`  
**R2:** Settings em 3 arquivos: `base.py`, `dev.py`, `test.py`  
**R3:** Docker Compose com PostgreSQL 17 + app  
**R4:** Template `base.html` com Bootstrap 5.3 CDN, tema hospitalar, PWA meta tags, navbar responsiva  
**R5:** `manifest.json` e `sw.js` (service worker) servidos como estáticos  
**R6:** `home.html` como landing page acessível na raiz `/`  
**R7:** `conftest.py` com fixtures pytest-django  
**R8:** Quality gate (ruff + mypy + pytest) configurado e passando

## Arquivos esperados

```
regula-vasc/
├── pyproject.toml
├── manage.py
├── conftest.py
├── docker-compose.yml
├── config/
│   ├── __init__.py
│   ├── wsgi.py
│   ├── asgi.py
│   ├── urls.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── dev.py
│       └── test.py
├── apps/
│   └── __init__.py
├── templates/
│   ├── base.html
│   └── home.html
└── static/
    ├── css/
    │   └── app.css
    ├── js/
    │   └── sw.js
    └── manifest.json
```

Arquivos proibidos: Nenhum arquivo dentro de `apps/*` exceto `__init__.py`. Não criar models, views ou urls de apps ainda.

## TDD obrigatório

### RED
- Teste: `test_home_page_returns_200` (client GET `/` → 200)
- Teste: `test_home_page_uses_base_template`
- Teste: `test_static_files_served` (manifest.json, app.css acessíveis em DEBUG)
- Teste: `test_pwa_meta_tags_present` (viewport, theme-color, apple-mobile-web-app-capable no base.html)

### GREEN
- Criar `config/settings/base.py` com INSTALLED_APPS, DATABASES (via dj-database-url), middleware, TEMPLATES, STATIC_URL, MEDIA_URL
- Criar `config/settings/dev.py` com DEBUG=True, SECRET_KEY de env
- Criar `config/settings/test.py` com banco SQLite em memória para testes
- Criar `config/urls.py` com rota `/` servindo TemplateView para `home.html`
- Criar `templates/base.html` e `templates/home.html`
- Criar `static/manifest.json`, `static/js/sw.js`, `static/css/app.css`

### REFACTOR
- DRY: settings base/dev/test seguem padrão de herança limpa
- Verificar que `pyproject.toml` tem todas as dependências necessárias

## Checks de inspeção obrigatórios

```bash
rg -n "viewport|theme-color|apple-mobile-web-app" templates/base.html
rg -n "manifest" templates/base.html
rg -n "serviceWorker\|sw.js" static/js/sw.js templates/base.html
rg -n "bootstrap" templates/base.html
rg -n "DJANGO_SETTINGS_MODULE" pyproject.toml
```

## Critérios de sucesso

- [ ] `uv run manage.py runserver` inicia sem erros
- [ ] `http://localhost:8000/` retorna home.html
- [ ] `http://localhost:8000/static/manifest.json` retorna JSON válido
- [ ] `uv run pytest` passa com pelo menos 4 testes
- [ ] `uv run ruff check .` passa
- [ ] `uv run ruff format --check .` passa
- [ ] `uv run mypy .` passa (com configuração mínima)
- [ ] `docker-compose up` sobe PostgreSQL e app

## Gates de autoavaliação

1. O projeto inicia com `uv run manage.py runserver`?
2. O template base.html contém todas as meta tags PWA obrigatórias?
3. O manifest.json é JSON válido e contém name, icons, theme_color?
4. Os 3 arquivos de settings (base/dev/test) funcionam sem import circular?
5. pytest encontra e executa os testes sem erro de configuração?

## Relatório obrigatório

Crie `/tmp/bootstrap-regulavasc-core-slice-000-report.md` com:
- Status (COMPLETE/INCOMPLETE)
- Matriz requisito → arquivo(s) → teste(s)
- RED: comandos e output
- GREEN: comandos e output
- Snippets antes/depois
- Checks de inspeção (comandos `rg` executados e interpretação)
- Pytest baseline vs final
- Quality gate completo
- Respostas aos gates de autoavaliação
- Handoff para verificador (arquivos alterados, comandos para rerun, riscos, checklist R1-R8)

---

**Implement ONLY this slice.** Follow the protocol above. Do not create any app models, views, or urls beyond the bootstrap structure. Run quality gate, update `tasks.md` only if all checks pass, create the report, commit and push, reply with REPORT_PATH and stop.
