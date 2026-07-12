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
    "art17": {
        "title": "Establish a Quality Management System",
        "description": (
            "Article 17 requires providers of high-risk AI systems to put a "
            "documented quality management system in place."
        ),
        "article": "Art. 17",
        "template": "art17/quality_management_system.py",
        "extra_templates": [],
        "steps": [
            "Create a QMSDocument and commit docs/quality-management.md",
            "Record testing/validation procedures (Art. 17(1)(d)-(g))",
            "Record the accountability framework (Art. 17(1)(n))",
            "Review the QMS every release",
        ],
    },
    "art26": {
        "title": "Implement Deployer Obligations",
        "description": (
            "Article 26 requires deployers of high-risk AI systems to assign "
            "trained oversight staff, monitor operation, retain logs, and "
            "inform individuals subject to AI-assisted decisions."
        ),
        "article": "Art. 26",
        "template": "art26/deployer_obligations.py",
        "extra_templates": [],
        "steps": [
            "Assign and document trained human oversight staff",
            "Add an incident-reporting procedure to the provider/authority",
            "Configure log retention for at least 6 months (Art. 26(6))",
            "Notify individuals subject to a high-risk AI-assisted decision",
        ],
    },
    "art27": {
        "title": "Conduct a Fundamental Rights Impact Assessment",
        "description": (
            "Article 27 requires certain deployers to assess the impact on "
            "fundamental rights before first using a high-risk AI system."
        ),
        "article": "Art. 27",
        "template": "art27/fria.py",
        "extra_templates": [],
        "steps": [
            "Verify whether your deployment falls in Art. 27's scope",
            "Complete a FRIA with FundamentalRightsImpactAssessment",
            "Document mitigation measures and a complaint/redress path",
            "Commit docs/fria.md before first use",
        ],
    },
    "art6": {
        "title": "Document Intended Purpose and Annex III Classification",
        "description": (
            "Article 6 classification of a system as high-risk turns on its "
            "documented intended purpose and the specific Annex III category "
            "it falls under."
        ),
        "article": "Art. 6",
        "template": "art6/intended_purpose_classification.py",
        "extra_templates": [],
        "steps": [
            "Fill in IntendedPurposeClassification with purpose and context",
            "Identify the specific Annex III category, or 'none'",
            "Generate docs/intended-purpose.md with write_classification()",
            "Re-classify whenever the intended purpose or context changes",
        ],
    },
    "art5": {
        "title": "Halt and Escalate a Prohibited AI Practice",
        "description": (
            "Article 5 prohibits certain AI practices outright. There is no "
            "configuration that makes a prohibited practice compliant — the "
            "only fix is removal, or a documented legal determination that "
            "the match was a false positive."
        ),
        "article": "Art. 5",
        "template": "art5/prohibited_practice_escalation.py",
        "extra_templates": [],
        "steps": [
            "Do not deploy the flagged functionality",
            "Escalate to qualified legal/compliance review immediately",
            "Record the determination with ProhibitedPracticeRecord",
            "Wire require_clearance() into your deployment gate so the "
            "block is enforced, not just documented",
        ],
    },
    "art13": {
        "title": "Provide Instructions for Use to Deployers",
        "description": (
            "Article 13 requires high-risk AI systems to be accompanied by "
            "clear instructions covering intended purpose, accuracy, "
            "limitations, and how to interpret outputs."
        ),
        "article": "Art. 13",
        "template": "art13/instructions_for_use.py",
        "extra_templates": [],
        "steps": [
            "Fill in InstructionsForUse with purpose, accuracy, and limitations",
            "Document output-interpretation guidance and input requirements",
            "Generate docs/instructions.md with write_instructions()",
            "Give the document to every deployer before first use",
        ],
    },
    "art15": {
        "title": "Harden Accuracy, Robustness, and Cybersecurity",
        "description": (
            "Article 15 requires high-risk AI systems to reach an appropriate "
            "accuracy level, be resilient to errors and manipulation, and be "
            "protected against unauthorized access."
        ),
        "article": "Art. 15",
        "template": "art15/robustness_and_security.py",
        "extra_templates": [],
        "steps": [
            "Wrap model calls with @guarded_call for retries and a safe fallback",
            "Add validate_input() and a RateLimiter at the AI-facing boundary",
            "Record measurements with AccuracyLog every evaluation run",
            "Add adversarial/edge-case tests alongside the normal test suite",
        ],
    },
    "art16": {
        "title": "Verify Provider Obligations Are Met",
        "description": (
            "Article 16 requires providers of high-risk AI systems to satisfy "
            "quality management, technical documentation, logging, "
            "post-market monitoring, and incident reporting obligations."
        ),
        "article": "Art. 16",
        "template": "art16/provider_obligations_checklist.py",
        "extra_templates": [],
        "steps": [
            "Run check_provider_obligations() against your actual artifacts",
            "Close every gap it reports (see the Art. 9/11/12/17 fixes)",
            "Generate PROVIDER_OBLIGATIONS.md with write_report()",
            "Re-run the checklist before every release",
        ],
    },
    "art24": {
        "title": "Verify Provider Compliance Before Distribution",
        "description": (
            "Article 24 requires distributors to verify the provider's "
            "conformity assessment, technical documentation, and "
            "instructions of use before making a high-risk system available."
        ),
        "article": "Art. 24",
        "template": "art24/distributor_verification.py",
        "extra_templates": [],
        "steps": [
            "Record a ProviderVerification before shipping each version",
            "Call require_clearance_to_distribute() in your release script",
            "Report non-conformance to the provider/authority if found",
            "Keep distributor_record.json in version control",
        ],
    },
    "art43": {
        "title": "Complete Conformity Assessment and EU Database Registration",
        "description": (
            "Article 43 requires a conformity assessment before market "
            "placement; Article 49 requires EU database registration before "
            "the system is placed on the market or put into service."
        ),
        "article": "Art. 43",
        "template": "art43/conformity_assessment.py",
        "extra_templates": [],
        "steps": [
            "Complete a ConformityAssessment covering Art. 9-15 requirements",
            "Confirm assessment.passed before proceeding",
            "Generate docs/conformity-assessment.md with write_report()",
            "Register in the EU database and record it with "
            "write_registration_record() before deployment",
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
    "vercel_generation": "art50",
    "vercel_tools": "art14",
    "vercel_agent_loop": "art14",
    "vercel_structured_output": "art11",
}

# Any provider usage warrants technical documentation.
PROVIDER_RULE = "art11"
