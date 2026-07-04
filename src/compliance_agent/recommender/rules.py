"""Maps findings and gaps to fix templates.

FIX_RULES describes one fix per article. TRIGGER_TO_RULE maps concrete
finding categories and gap ids to the rule that fixes them. Provider findings
(any `provider:*` category) map to Art. 11 technical documentation.
"""

FIX_RULES: dict[str, dict] = {
    "art50": {
        "title": "Add AI Transparency Disclosure",
        "description": (
            "Article 50 requires users to be informed they are interacting with an AI system."
        ),
        "article": "Art. 50",
        "template": "art50/transparency_notice.py",
        "extra_templates": [
            "art50/content_marking.py",
            "art50/deepfake_disclosure.py",
            "common/ai_disclosure_banner.html",
            "common/ai_disclosure_middleware.py",
        ],
        "steps": [
            "Import the transparency notice module",
            "Add the middleware to your web framework",
            "Display the notice before the first AI interaction",
            "Add x-ai-disclosure headers to API responses",
            "Mark generated content with machine-readable markers",
        ],
    },
    "art12": {
        "title": "Implement Event Logging",
        "description": ("Article 12 requires logging of AI system events for traceability."),
        "article": "Art. 12",
        "template": "art12/event_logging.py",
        "extra_templates": [],
        "steps": [
            "Add AILogger to your project",
            "Wrap AI function calls with @log_ai_call",
            "Configure log retention (minimum 6 months)",
            "Schedule cleanup_expired() for log rotation",
        ],
    },
    "art14": {
        "title": "Add Human Oversight Mechanism",
        "description": (
            "Article 14 requires effective human oversight for high-risk AI "
            "systems, including autonomous agent actions."
        ),
        "article": "Art. 14",
        "template": "art14/human_oversight.py",
        "extra_templates": [],
        "steps": [
            "Identify high-stakes decision points",
            "Add HumanOversightCheckpoint at those points",
            "Configure the approval workflow per risk level",
            "Keep the oversight audit trail under retention",
        ],
    },
    "art9": {
        "title": "Establish a Risk Management System",
        "description": (
            "Article 9 requires a continuous risk management process for high-risk AI systems."
        ),
        "article": "Art. 9",
        "template": "art9/risk_management.py",
        "extra_templates": [],
        "steps": [
            "Create a RiskRegister and commit risk_register.json",
            "Identify risks to health, safety, and fundamental rights",
            "Record a mitigation and an owner per risk",
            "Review the register every release (mark_reviewed)",
        ],
    },
    "art10": {
        "title": "Document Data Governance",
        "description": (
            "Article 10 requires documented governance for training, validation, and testing data."
        ),
        "article": "Art. 10",
        "template": "art10/data_governance.py",
        "extra_templates": [],
        "steps": [
            "Create a DatasetCard for each dataset",
            "Record provenance and the collection process",
            "Run the governance checklist before training",
            "Track known gaps with a remediation plan",
        ],
    },
    "art11": {
        "title": "Create Technical Documentation",
        "description": (
            "Article 11 requires technical documentation describing the AI "
            "system, its purpose, architecture, and limitations."
        ),
        "article": "Art. 11",
        "template": "art11/technical_documentation.py",
        "extra_templates": ["common/compliance_config.yaml"],
        "steps": [
            "Fill in a SystemDescription for your AI system",
            "Generate TECHNICAL_DOC.md with write_documentation()",
            "Commit the document and update it every release",
            "Fill in compliance_config.yaml to record your declared posture "
            "(for your records/auditors — not yet read by the scanner)",
        ],
    },
}

# Finding categories (from detectors) that trigger each rule. Gaps map to
# rules directly by article number in the recommender engine.
# Mappings are grouped by what the construct actually implies, not by which
# article "feels" related:
#   agents / tools / multi-agent / orchestration -> human oversight (Art. 14)
#   memory / checkpoints / chat / task history    -> record-keeping  (Art. 12)
#   chains / graphs / processes (composition)      -> technical docs  (Art. 11)
# Transparency (Art. 50) is driven only by user-interaction detection, never by
# a framework construct on its own — a chain or assistant class does not by
# itself mean the system is user-facing.
TRIGGER_TO_RULE: dict[str, str] = {
    "pattern:chat-interface": "art50",
    "pattern:user-input": "art50",
    "pattern:missing-logging": "art12",
    "agent:tool-calls": "art14",
    "agent:multi-agent": "art14",
    "agent:mcp": "art14",
    "pattern:data-processing": "art10",
    # framework detectors
    "langchain_agent": "art14",
    "langchain_tools": "art14",
    "langchain_memory": "art12",
    "langchain_chain": "art11",
    "crewai_crew": "art14",
    "crewai_agent": "art14",
    "crewai_task": "art12",
    "crewai_memory": "art12",
    "crewai_process": "art11",
    "autogen_assistant": "art14",
    "autogen_userproxy": "art14",
    "autogen_groupchat": "art14",
    "autogen_tools": "art14",
    "autogen_chat": "art12",
    "langgraph_graph": "art11",
    "langgraph_conditional": "art14",
    "langgraph_tools": "art14",
    "langgraph_checkpoint": "art12",
}

# Any provider usage warrants technical documentation.
PROVIDER_RULE = "art11"
