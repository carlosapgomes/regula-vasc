# Proposal: Bootstrap RegulaVasc Core

## Why

O Hospital Metropolitano Humaitá (HMH) precisa de um sistema de apoio à regulação médica para cirurgia vascular. Atualmente o processo é manual: o enfermeiro recebe relatórios de regulação em PDF, extrai dados manualmente e encaminha ao médico por WhatsApp. O médico avalia "de cabeça" e responde também por WhatsApp. Não há rastreabilidade, auditoria ou métricas. O projeto `ats-web` já provou o conceito para EDA (Endoscopia Digestiva Alta) — agora precisamos de uma versão simplificada e focada exclusivamente no fluxo de triagem vascular.

## What Changes

- **Novo projeto Django SSR** `regula-vasc` — monolito com 7 apps: accounts, cases, llm, pipeline, intake, doctor, dashboard
- **Três papéis de usuário**: enfermeiro (upload e ciência), médico (parecer aceite/recusa), administrador (dashboard e encerramento)
- **Upload de PDF** do relatório de regulação pelo enfermeiro, com extração automática de texto
- **Pipeline LLM em 2 etapas**: LLM1 extrai dados estruturados (paciente, lesão, pulsos, exames, antecedentes) via schema Pydantic; LLM2 emite parecer de aceite/recusa baseado em critérios de cirurgia vascular
- **Dual-LLM**: suporte a execução paralela de dois modelos LLM para comparação, com habilitação/desabilitação pelo administrador
- **Fila médica**: médico visualiza dados estruturados, pareceres dos LLMs e PDF original; decide aceitar ou recusar com justificativa obrigatória na recusa e observação opcional
- **Ciência do enfermeiro**: após decisão médica, caso volta à fila do enfermeiro para confirmação de recebimento
- **Dashboard administrativo**: métricas de fluxo, fila completa com filtros, encerramento administrativo de qualquer caso
- **Anexos complementares**: upload de arquivos adicionais (PDF, JPEG, PNG) pelo enfermeiro
- **Comunicação intra-app**: thread de mensagens operacionais por caso, evitando WhatsApp para discutir pacientes
- **PWA**: installável em dispositivos móveis, com service worker e manifesto
- **Autenticação**: login tradicional Django com multi-role (troca de papel via avatar), fluxo de password reset, admin pode gerenciar usuários

## Capabilities

### New Capabilities

- `accounts`: Autenticação, modelo User multi-role (nurse/doctor/admin), switch-role, perfil, password reset, convite de usuário
- `cases`: Modelo Case com FSM (~9 estados), CaseEvent (auditoria), CaseAttachment (anexos), CaseCommunicationMessage (thread operacional)
- `llm`: PromptTemplate versionado, seed de prompts vasculares (baseados no matrix-pdf-summarizer-bot)
- `pipeline`: Pipeline LLM em 2 etapas (LLM1 extração + LLM2 sugestão), schemas Pydantic para dados vasculares, suporte a múltiplos providers (OpenAI, Anthropic, Ollama, generic), dual-LLM paralelo
- `intake`: Upload de PDF pelo enfermeiro, fila "meus casos", detalhe com timeline/stepper/PDF viewer, confirmação de ciência, lock system para evitar conflitos
- `doctor`: Fila médica, tela de decisão (aceite/recusa) com visão lado-a-lado dos pareceres dual-LLM, presenter de relatório vascular formatado
- `dashboard`: Métricas de fluxo (total, aceitos, recusados, pendentes, tempos médios), tabela de todos os casos com filtros/busca, encerramento administrativo, gestão de usuários e prompts, configuração dos providers LLM
- `pwa`: Service worker, manifest.json, tema hospitalar mobile-first com Bootstrap 5.3

### Modified Capabilities

_Nenhuma — este é um projeto greenfield._

## Impact

- **Novo repositório/projeto**: `regula-vasc/` (diretório já existe, vazio)
- **Dependências**: Django 5.2, django-fsm 3.0.1, django-q2, pymupdf, openai, pydantic v2, psycopg, whitenoise, gunicorn, python-dotenv, dj-database-url
- **Banco de dados**: PostgreSQL 17 (via docker-compose)
- **APIs externas**: OpenAI (ou compatível), Anthropic (opcional), providers generic (Ollama, etc.)
- **Referência**: Código adaptado do `ats-web` (models, views, templates, tests) e prompts do `matrix-pdf-summarizer-bot`
- **Infraestrutura**: Docker Compose para dev, whitenoise para servir estáticos, gunicorn para produção
