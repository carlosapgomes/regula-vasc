"""Presenter for doctor case report — generates formatted HTML from structured data.

Builds a comprehensive vascular report with all sections from the LLM1 schema.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# ── Helper utilities ────────────────────────────────────────────────────────


def _val(value: Any, default: str = "—") -> str:
    """Return the string representation of a value, or a default dash."""
    if value is None:
        return default
    s = str(value)
    return s if s.strip() else default


def _flag(value: str | None, default: str = "—") -> str:
    """Translate evidence flag ('yes'/'no'/'unknown') to Portuguese."""
    if value is None:
        return default
    mapping: dict[str, str] = {
        "yes": "Sim",
        "no": "Não",
        "unknown": "Não informado",
    }
    return mapping.get(value, value)


def _build_section(title: str, rows: list[tuple[str, str]]) -> str:
    """Build an HTML table section from label-value pairs."""
    if not rows:
        return ""
    lines = [
        f'<h5 class="report-section-title">{title}</h5>',
        '<table class="table table-sm table-borderless report-table">',
    ]
    for label, value in rows:
        lines.append(
            f"  <tr><td class='report-label'><strong>{label}</strong></td><td class='report-value'>{value}</td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


def _build_list_section(title: str, items: list[str]) -> str:
    """Build an HTML section from a list of items."""
    if not items:
        return ""
    lines = [
        f'<h5 class="report-section-title">{title}</h5>',
        "<ul class='report-list'>",
    ]
    for item in items:
        lines.append(f"  <li>{item}</li>")
    lines.append("</ul>")
    return "\n".join(lines)


def _pulse_display(pulse: Any) -> str:
    """Format pulse notation with CSS class."""
    if pulse is None:
        return '<span class="pulse-na">—</span>'
    cls = {
        "3+": "pulse-strong",
        "2+": "pulse-normal",
        "1+": "pulse-weak",
        "0": "pulse-absent",
        "-": "pulse-absent-doppler",
        "?": "pulse-unknown",
    }.get(str(pulse), "pulse-unknown")
    return f'<span class="{cls}">{pulse}</span>'


# ── Section builders ────────────────────────────────────────────────────────


def _build_patient(data: dict[str, Any]) -> str:
    patient = data.get("patient", {}) or {}
    if isinstance(patient, dict) and not any(v for v in patient.values() if v is not None):
        return ""

    rows: list[tuple[str, str]] = [
        ("Nome", _val(patient.get("name"))),
        ("Idade", _val(patient.get("age"))),
        ("Sexo", _val(patient.get("sex"))),
    ]
    return _build_section("Dados do Paciente", rows)


def _build_referral(data: dict[str, Any]) -> str:
    referral = data.get("referral", {}) or {}
    if isinstance(referral, dict) and not any(v for v in referral.values() if v is not None):
        return ""

    limb_map: dict[str, str] = {
        "left": "Esquerdo",
        "right": "Direito",
        "bilateral": "Bilateral",
        "unknown": "Não informado",
    }
    rows: list[tuple[str, str]] = [
        ("Queixa Principal", _val(referral.get("main_complaint"))),
        ("Tempo de Evolução (dias)", _val(referral.get("evolution_time_days"))),
        ("Membro Acometido", limb_map.get(str(referral.get("affected_limb", "unknown")), "Não informado")),
        ("Diagnóstico Suspeito", _val(referral.get("suspected_diagnosis"))),
    ]
    return _build_section("Queixa e Evolução", rows)


def _build_lesion(data: dict[str, Any]) -> str:
    lesion = data.get("lesion", {}) or {}
    if isinstance(lesion, dict) and not any(v for v in lesion.values() if v is not None):
        return ""

    depth_map: dict[str, str] = {
        "superficial": "Superficial",
        "profunda": "Profunda",
        "expondo_osso": "Expondo osso",
        "expondo_tendao": "Expondo tendão",
        "unknown": "Não informado",
    }
    necrosis_map: dict[str, str] = {
        "seca": "Seca",
        "umida": "Úmida",
        "gasosa": "Gasosa",
        "none": "Nenhuma",
        "unknown": "Não informado",
    }
    rows: list[tuple[str, str]] = [
        ("Localização", _val(lesion.get("exact_location"))),
        ("Tamanho (cm)", _val(lesion.get("size_cm"))),
        ("Profundidade", depth_map.get(str(lesion.get("depth", "unknown")), "Não informado")),
        ("Aspecto", _val(lesion.get("aspect"))),
        ("Odor", _flag(lesion.get("odor"))),
        ("Larvas", _flag(lesion.get("larvae"))),
        ("Localização Gangrena", _val(lesion.get("gangrene_location"))),
        ("Tipo de Necrose", necrosis_map.get(str(lesion.get("necrosis_type", "unknown")), "Não informado")),
        ("Secreção Purulenta", _flag(lesion.get("purulent_secretion"))),
    ]
    return _build_section("Lesão", rows)


def _build_pain(data: dict[str, Any]) -> str:
    pain = data.get("pain", {}) or {}
    if isinstance(pain, dict) and not any(v for v in pain.values() if v is not None):
        return ""

    rows: list[tuple[str, str]] = [
        ("Dor Presente", _flag(pain.get("has_pain"))),
        ("Dor em Repouso", _flag(pain.get("rest_pain"))),
        ("Dor Noturna", _flag(pain.get("night_pain"))),
        ("Melhora com Suspensão", _flag(pain.get("improves_with_dangling"))),
        ("Claudicação Prévio", _flag(pain.get("prior_claudication"))),
        ("Início Súbito", _flag(pain.get("sudden_onset"))),
    ]
    return _build_section("Dor", rows)


def _build_pulses(data: dict[str, Any]) -> str:
    pulses = data.get("pulses", {}) or {}
    if isinstance(pulses, dict) and not any(v for v in pulses.values() if v is not None):
        return ""

    rows: list[tuple[str, str]] = [
        ("Femoral D", _pulse_display(pulses.get("femoral_r"))),
        ("Femoral E", _pulse_display(pulses.get("femoral_l"))),
        ("Poplíteo D", _pulse_display(pulses.get("popliteal_r"))),
        ("Poplíteo E", _pulse_display(pulses.get("popliteal_l"))),
        ("Tibial Posterior D", _pulse_display(pulses.get("tibial_posterior_r"))),
        ("Tibial Posterior E", _pulse_display(pulses.get("tibial_posterior_l"))),
        ("Pedal D", _pulse_display(pulses.get("pedal_r"))),
        ("Pedal E", _pulse_display(pulses.get("pedal_l"))),
    ]
    return _build_section("Pulsos", rows)


def _build_history(data: dict[str, Any]) -> str:
    history = data.get("history", {}) or {}
    if isinstance(history, dict) and not any(v for v in history.values() if v is not None):
        return ""

    label_map: dict[str, str] = {
        "diabetes": "Diabetes",
        "smoking": "Tabagismo",
        "hypertension": "Hipertensão",
        "ckd": "Doença Renal Crônica (DRC)",
        "mi": "Infarto Agudo do Miocárdio (IAM)",
        "stroke": "Acidente Vascular Cerebral (AVC)",
        "arrhythmia": "Arritmia",
        "heart_failure": "Insuficiência Cardíaca (ICC)",
        "copd": "Doença Pulmonar Obstrutiva Crônica (DPOC)",
        "prior_amputation": "Amputação Prévia",
        "prior_revascularization": "Revascularização Prévia",
        "anticoagulation_use": "Uso de Anticoagulante",
        "antiplatelet_use": "Uso de Antiagregante Plaquetário",
    }
    rows: list[tuple[str, str]] = []
    for key, label in label_map.items():
        value = history.get(key)
        if value is not None:
            rows.append((label, _flag(value)))
    return _build_section("Antecedentes", rows)


def _build_labs(data: dict[str, Any]) -> str:
    labs = data.get("labs", {}) or {}
    if isinstance(labs, dict) and not any(v for v in labs.values() if v is not None):
        return ""

    label_map: dict[str, str] = {
        "hemoglobin": "Hemoglobina (g/dL)",
        "leukocytes": "Leucócitos (/mm³)",
        "crp": "Proteína C Reativa (mg/L)",
        "glucose": "Glicemia (mg/dL)",
        "creatinine": "Creatinina (mg/dL)",
        "urea": "Ureia (mg/dL)",
        "potassium": "Potássio (mEq/L)",
        "lactate": "Lactato (mmol/L)",
    }
    unit_map: dict[str, str] = {
        "hemoglobin": " g/dL",
        "leukocytes": " /mm³",
        "crp": " mg/L",
        "glucose": " mg/dL",
        "creatinine": " mg/dL",
        "urea": " mg/dL",
        "potassium": " mEq/L",
        "lactate": " mmol/L",
    }
    rows: list[tuple[str, str]] = []
    for key, label in label_map.items():
        value = labs.get(key)
        if value is not None:
            unit = unit_map.get(key, "")
            rows.append((label, f"{_val(value)}{unit}"))
    return _build_section("Exames Laboratoriais", rows)


def _build_edema(data: dict[str, Any]) -> str:
    edema = data.get("edema", {}) or {}
    if isinstance(edema, dict) and not any(v for v in edema.values() if v is not None):
        return ""

    ub_map: dict[str, str] = {
        "unilateral": "Unilateral",
        "bilateral": "Bilateral",
        "none": "Ausente",
        "unknown": "Não informado",
    }
    rows: list[tuple[str, str]] = [
        ("Edema Presente", _flag(edema.get("present"))),
        ("Unilateral/Bilateral", ub_map.get(str(edema.get("unilateral_bilateral", "unknown")), "Não informado")),
        ("Depressível", _flag(edema.get("depressible"))),
        ("Endurecido", _flag(edema.get("hardened"))),
        ("Quente", _flag(edema.get("hot"))),
        ("Frio", _flag(edema.get("cold"))),
    ]
    return _build_section("Edema", rows)


def _build_infection(data: dict[str, Any]) -> str:
    infection = data.get("infection", {}) or {}
    if isinstance(infection, dict) and not any(v for v in infection.values() if v is not None):
        return ""

    local_signs: list[str] = infection.get("local_signs", []) or []
    systemic_signs: list[str] = infection.get("systemic_signs", []) or []

    parts = ""
    if local_signs:
        parts += _build_list_section("Sinais Locais", local_signs)
    if systemic_signs:
        parts += _build_list_section("Sinais Sistêmicos", systemic_signs)
    return parts


def _build_imaging(data: dict[str, Any]) -> str:
    imaging = data.get("imaging", {}) or {}
    if isinstance(imaging, dict) and not any(v for v in imaging.values() if v is not None):
        return ""

    rows: list[tuple[str, str]] = [
        ("Raio-X", _val(imaging.get("xray"))),
        ("Duplex", _val(imaging.get("duplex"))),
        ("Angiotomografia", _val(imaging.get("angiotomography"))),
    ]
    return _build_section("Exames de Imagem", rows)


def _build_acute_ischemia(data: dict[str, Any]) -> str:
    ai = data.get("acute_ischemia", {}) or {}
    if isinstance(ai, dict) and not any(v for v in ai.values() if v is not None):
        return ""

    rutherford_map: dict[str, str] = {
        "I": "I",
        "IIa": "IIa",
        "IIb": "IIb",
        "III": "III",
        "unknown": "Não informado",
    }
    signs: list[str] = ai.get("signs", []) or []
    parts = ""
    rows: list[tuple[str, str]] = [
        ("Categoria Rutherford", rutherford_map.get(str(ai.get("rutherford_category", "unknown")), "Não informado")),
        ("Tempo de Início (horas)", _val(ai.get("time_onset_hours"))),
    ]
    parts += _build_section("Isquemia Aguda", rows)
    if signs:
        parts += _build_list_section("Sinais de Isquemia Aguda", signs)
    return parts


# ── Main presenter ──────────────────────────────────────────────────────────


def build_report(structured_data: dict[str, Any] | None) -> str:
    """Build a formatted HTML report from LLM1 structured data.

    Returns an HTML string containing all vascular sections.
    If structured_data is None, returns an empty message.
    """
    if structured_data is None:
        return '<div class="report-empty text-muted">Dados estruturados não disponíveis.</div>'

    parts: list[str] = ['<div class="doctor-report">']

    section_builders: list[Callable[[dict[str, Any]], str]] = [
        _build_patient,
        _build_referral,
        _build_lesion,
        _build_pain,
        _build_pulses,
        _build_history,
        _build_labs,
        _build_edema,
        _build_infection,
        _build_imaging,
        _build_acute_ischemia,
    ]

    for builder in section_builders:
        section_html = builder(structured_data)
        if section_html:
            parts.append(section_html)

    # Extraction quality section
    eq = structured_data.get("extraction_quality", {}) or {}
    if isinstance(eq, dict) and eq.get("confidence"):
        confidence_map: dict[str, str] = {
            "alta": "Alta",
            "media": "Média",
            "baixa": "Baixa",
        }
        confidence = confidence_map.get(str(eq.get("confidence", "")), str(eq.get("confidence", "")))
        missing = eq.get("missing_fields", []) or []
        rows: list[tuple[str, str]] = [
            ("Confiança da Extração", confidence),
            ("Campos Ausentes", ", ".join(missing) if missing else "Nenhum"),
        ]
        parts.append(_build_section("Qualidade da Extração", rows))

    parts.append("</div>")
    return "\n".join(parts)


def prepare_doctor_case_report(structured_data: dict[str, Any] | None) -> str:
    """Alias for build_report — prepares the case report for the doctor view."""
    return build_report(structured_data)
