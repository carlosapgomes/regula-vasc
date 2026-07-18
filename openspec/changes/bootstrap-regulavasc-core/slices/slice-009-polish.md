# Slice 009 — Anexos e Polimento PWA

## Handoff

Leia: `proposal.md`, `design.md` (D9), `tasks.md`, `specs/pwa/spec.md`.  
Referências: `../../ats-web/templates/pdf_viewer/mobile_pdf_viewer.html`, `../../ats-web/templates/image_viewer/mobile_image_viewer.html`, `../../ats-web/static/js/pdf-viewer.js`, `../../ats-web/static/js/sw.js`, `../../ats-web/static/manifest.json`, `../../ats-web/static/icons/`.

**Estado atual:** Sistema funcional com todos os fluxos (S00-S08). PWA manifest e SW básicos existem (S00). Faltam viewers mobile, ícones completos, e polimento.

## Objetivo

Adicionar viewers mobile (PDF e imagens), completar ícones PWA, garantir installabilidade, testes de integração end-to-end.

## Escopo funcional

**R1:** `mobile_pdf_viewer.html`: viewer PDF usando PDF.js (jsDelivr CDN), com controles de zoom/navegação, back button seguro  
**R2:** `mobile_image_viewer.html`: viewer de imagem full-screen com back button  
**R3:** Integrar viewers nos fluxos intake, doctor e dashboard (links "Ver PDF" e "Ver Imagem" abrem viewer mobile)  
**R4:** Ícones PWA em todos os tamanhos (72, 96, 128, 144, 152, 192, 384, 512px) nos modos normal e contrast  
**R5:** Service worker com cache de estáticos e fallback offline  
**R6:** Teste de integração: fluxo completo upload → processamento (mock) → decisão médica → ciência → caso concluído  
**R7:** Validação final: quality gate completo, 0 failures, todos os slices anteriores continuam passando

## Arquivos esperados

```
templates/pdf_viewer/
└── mobile_pdf_viewer.html           # NOVO
templates/image_viewer/
└── mobile_image_viewer.html         # NOVO
static/js/
├── pdf-viewer.js                     # NOVO/atualizado
└── sw.js                             # ATUALIZADO: cache de estáticos
static/icons/
├── icon-72x72.png                    # NOVO
├── icon-96x96.png                    # NOVO
├── icon-128x128.png                  # NOVO
├── icon-144x144.png                  # NOVO
├── icon-152x152.png                  # NOVO
├── icon-192x192.png                  # NOVO
├── icon-384x384.png                  # NOVO
├── icon-512x512.png                  # NOVO
├── chd-base.svg                      # NOVO/adaptado
└── ... (variantes contrast)
static/manifest.json                  # ATUALIZADO: todos os ícones
templates/intake/case_detail.html     # MODIFICADO: links para viewers
templates/doctor/decision.html        # MODIFICADO: links para viewers
tests/
└── test_integration_flow.py          # NOVO: teste end-to-end
```

## TDD

**RED:**
- `test_mobile_pdf_viewer_accessible`: GET pdf_viewer/<case_id> → 200, contém PDF.js
- `test_mobile_pdf_viewer_404_without_pdf`: caso sem pdf → 404
- `test_mobile_image_viewer_accessible`: GET image_viewer → 200 para JPEG/PNG
- `test_mobile_image_viewer_rejects_pdf`: GET image_viewer para PDF → 404
- `test_integration_full_flow`: upload PDF → pipeline mock → doctor decide → nurse ack → CLEANED
- `test_manifest_valid_json`: GET manifest.json → JSON válido com name, icons, theme_color
- `test_service_worker_served`: GET sw.js → 200, contém `self.addEventListener`

## Checks

```bash
rg -n "pdf_viewer\|image_viewer\|mobile_pdf_viewer\|mobile_image_viewer" apps/intake/views.py apps/doctor/views.py apps/dashboard/views.py
rg -n "pdfjs\|pdf.mjs\|pdf.worker" templates/pdf_viewer/mobile_pdf_viewer.html
rg -n "CacheFirst\|NetworkFirst\|precacheAndRoute" static/js/sw.js
rg -n "\"icons\"\|\"sizes\"\|\"192x192\"\|\"512x512\"" static/manifest.json
```

## Critérios

- [ ] PDF viewer mobile funcional com navegação entre páginas
- [ ] Image viewer mobile funcional para JPEG e PNG
- [ ] Manifest.json contém todos os tamanhos de ícone
- [ ] Service worker faz cache de CSS, JS, ícones
- [ ] Teste de integração cobre fluxo completo
- [ ] Quality gate final: 0 failures, 0 errors, todas as slices anteriores ainda passam

---

**Implement ONLY this slice.** Este é o último slice. Não adicione novas features além das listadas. O foco é polimento e completude. Relatório em `/tmp/bootstrap-regulavasc-core-slice-009-report.md`.
