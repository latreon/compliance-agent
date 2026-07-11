# ComplianceAgent Fix Templates

Copy-pasteable, working code templates for EU AI Act compliance, organized by
article. Each template is a real Python module (or config file) you can drop
into your project and adapt.

## Index

| Template | Article | Purpose |
|----------|---------|---------|
| [`art50/transparency_notice.py`](art50/transparency_notice.py) | Art. 50 | Tell users they are interacting with AI (decorator + ASGI middleware) |
| [`art50/content_marking.py`](art50/content_marking.py) | Art. 50 | Machine-readable marking of AI-generated content |
| [`art50/deepfake_disclosure.py`](art50/deepfake_disclosure.py) | Art. 50 | Labeling for synthetic/deepfake media |
| [`art12/event_logging.py`](art12/event_logging.py) | Art. 12 | AI interaction logging with retention + cleanup |
| [`art14/human_oversight.py`](art14/human_oversight.py) | Art. 14 | Human-in-the-loop approval checkpoints with audit trail |
| [`art9/risk_management.py`](art9/risk_management.py) | Art. 9 | Lightweight risk register and review cycle |
| [`art10/data_governance.py`](art10/data_governance.py) | Art. 10 | Dataset provenance cards and governance checklist |
| [`art11/technical_documentation.py`](art11/technical_documentation.py) | Art. 11 | Annex IV-style technical documentation generator |
| [`art50/biometric_emotion_disclosure.py`](art50/biometric_emotion_disclosure.py) | Art. 50 | Emotion-recognition / biometric-categorisation exposure notice |
| [`art17/quality_management_system.py`](art17/quality_management_system.py) | Art. 17 | Quality management system documentation generator |
| [`art26/deployer_obligations.py`](art26/deployer_obligations.py) | Art. 26 | Deployer oversight staffing, incident reporting, decision notices |
| [`art27/fria.py`](art27/fria.py) | Art. 27 | Fundamental rights impact assessment generator |
| [`common/ai_disclosure_banner.html`](common/ai_disclosure_banner.html) | Art. 50 | Web UI disclosure banner (plain HTML/CSS) |
| [`common/ai_disclosure_middleware.py`](common/ai_disclosure_middleware.py) | Art. 50 | Flask and FastAPI disclosure middleware |
| [`common/compliance_config.yaml`](common/compliance_config.yaml) | — | Posture-declaration example (documentation only — see note) |

## Usage

1. Run `compliance-agent recommend .` to see which templates apply to your project.
2. Run `compliance-agent recommend . --output ./fixes` to copy the relevant
   templates (plus step-by-step instructions) into `./fixes`.
3. Copy the template into your codebase and adapt names, paths, and framework
   hooks to your stack.

## Note on `compliance_config.yaml`

This file is a **documentation artifact** for recording your declared EU AI Act
posture (intended purpose, declared tier, which obligations you have
implemented) for your own records and auditors. The scanner does **not** read it
yet — a project config file that changes scan behavior is on the
[roadmap](../README.md#roadmap). Copying it into your repo today has no effect on
scan results.

## Disclaimer

Templates are engineering starting points, not legal advice. Validate the final
implementation against the regulation text and your legal counsel.
