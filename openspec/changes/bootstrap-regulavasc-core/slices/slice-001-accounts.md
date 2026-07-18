# Slice 001 — Accounts (Autenticação e Papéis)

## Handoff para implementador LLM (contexto zero)

Antes de editar, leia:
- `openspec/changes/bootstrap-regulavasc-core/proposal.md`
- `openspec/changes/bootstrap-regulavasc-core/design.md`
- `openspec/changes/bootstrap-regulavasc-core/tasks.md`
- `openspec/changes/bootstrap-regulavasc-core/specs/accounts/spec.md`
- Projeto de referência: `../../ats-web/apps/accounts/` (models.py, views.py, urls.py, forms.py, decorators.py, context_processors.py, middleware.py, password_reset_views.py, profile_views.py, templates/accounts/*)

**Estado atual:** Projeto Django bootstrap funcionando (S00). Não há apps instalados além dos defaults Django.

## Protocolo obrigatório para implementador DeepSeek4-Flash

[Idêntico ao do slice-000 — baseline, RED, GREEN, quality gate, relatório]

### Condições automáticas de INCOMPLETO

[Idêntico ao do slice-000]

## Objetivo

Criar o app `accounts` com modelo User customizado multi-role, sistema de autenticação (login/logout), switch de papel ativo, perfil, password reset, decorator `@role_required`, e seed de admin inicial. Ao final, deve ser possível criar usuários com papéis, logar, trocar de papel e ter acesso restrito por papel.

## Escopo funcional

**R1:** Modelo `User(AbstractUser)` com `account_status`, `professional_council` (CRM/COREN), `professional_council_number`, M2M para `Role`  
**R2:** Modelo `Role` com 3 registros seedados: nurse, doctor, admin  
**R3:** Login/logout com templates estilizados no tema hospitalar  
**R4:** Switch de papel ativo armazenado na sessão (`active_role`), acessível via context processor  
**R5:** Perfil: visualização e edição de nome, email, registro profissional  
**R6:** Password reset: fluxo completo Django (email em console no dev)  
**R7:** Decorator `@role_required('nurse')` / `@role_required('doctor')` / `@role_required('admin')`  
**R8:** Comando `seed_admin` para criar admin inicial  
**R9:** Navbar no base.html reflete usuário logado e papel ativo  

## Arquivos esperados

```
apps/accounts/
├── __init__.py, apps.py, admin.py
├── models.py              # User, Role, ProfessionalCouncil
├── forms.py               # LoginForm, ProfileForm, UserCreationForm (admin)
├── views.py               # login, logout, switch_role
├── profile_views.py       # profile, password_change
├── password_reset_views.py
├── urls.py
├── decorators.py           # @role_required
├── context_processors.py   # active_role, app_display_name
├── middleware.py            # active_role na sessão
├── services.py             # create_user, etc.
├── migrations/
│   ├── 0001_initial.py
│   └── 0002_seed_roles.py
├── management/commands/
│   └── seed_admin.py
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_views.py
    ├── test_decorators.py
    └── test_password_reset.py
templates/accounts/
├── login.html
├── profile.html
├── switch_role.html
├── password_change_form.html
├── password_change_done.html
├── password_reset_form.html
├── password_reset_done.html
├── password_reset_confirm.html
├── password_reset_complete.html
└── email/
    ├── password_reset_email.html
    ├── password_reset_email.txt
    └── password_reset_subject.txt
```

Arquivos a modificar:
- `config/settings/base.py`: adicionar `apps.accounts` ao INSTALLED_APPS, AUTH_USER_MODEL, config de email
- `config/urls.py`: incluir `apps.accounts.urls`
- `templates/base.html`: integrar navbar com user info, role switch, botão logout

## TDD obrigatório

### RED
- `test_user_creation_with_role`: criar User, atribuir Role, verificar `user.roles.exists()`
- `test_login_success`: POST credentials válidos → redirect 302
- `test_login_failure`: POST credentials inválidos → 200 com erro
- `test_role_required_blocks_wrong_role`: user com role nurse acessa view decorada com `@role_required('doctor')` → redirect
- `test_role_required_allows_correct_role`: user com role doctor acessa view decorada com `@role_required('doctor')` → 200
- `test_switch_role_changes_active_role`: POST switch_role → session['active_role'] atualizado
- `test_password_reset_email_sent`: POST email → email enviado (mail.outbox no test)

### GREEN
Implementar na ordem: models → admin → forms → views → templates → urls → decorators → context processor

### REFACTOR
- DRY: evitar duplicação entre profile_views e password_reset_views
- Garantir que `professional_council` e `professional_council_number` são validados juntos no `clean()`

## Checks de inspeção obrigatórios

```bash
rg -n "role_required" apps/accounts/decorators.py
rg -n "active_role" apps/accounts/context_processors.py apps/accounts/middleware.py
rg -n "AUTH_USER_MODEL" config/settings/base.py
rg -n "@login_required" apps/accounts/views.py apps/accounts/profile_views.py
rg -n "switch.role\|switch_role\|Switch Role" templates/base.html
rg -n "account_status\|is_account_active" apps/accounts/models.py
```

## Critérios de sucesso

- [ ] Migration cria tabelas User, Role, user_roles
- [ ] Seed cria roles nurse, doctor, admin
- [ ] Login/logout funcional com templates
- [ ] Switch role atualiza navbar e libera views do papel
- [ ] `@role_required` bloqueia acesso errado
- [ ] Password reset envia email
- [ ] `seed_admin` cria superuser funcional
- [ ] Todos os testes passam

## Gates de autoavaliação

1. Usuário com 2 roles consegue trocar entre eles e acessar views diferentes?
2. Usuário sem role `doctor` é bloqueado ao acessar `/doctor/queue/` (quando existir)?
3. Password reset envia email com link válido?
4. `professional_council` sem `professional_council_number` dispara ValidationError?
5. O navbar mostra o nome do usuário e papel ativo corretamente?

---

**Implement ONLY this slice.** Follow the protocol. Do not create models/views for other apps. Update `tasks.md` only if all checks pass, create `/tmp/bootstrap-regulavasc-core-slice-001-report.md`, commit and push, reply with REPORT_PATH and stop.
