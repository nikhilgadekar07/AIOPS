SYSTEM = (
    "You are a senior engineering lead turning an approved spec into an implementation plan. "
    "Return only JSON with actionable file-level changes, explicit validation steps, and a ready-to-implement status."
)

TEMPLATE = """Requirement title: {title}
Requirement description: {description}

Approved specification:
{spec_json}

Relevant codebase context:
{codebase_context}

Generate a concise but actionable implementation plan in JSON with this exact shape:
{{
  "status": "ready",
  "files": ["path/to/file.py"],
  "changes": [
    {{
      "file": "path/to/file.py",
      "action": "update",
      "summary": "What changes are needed",
      "validation": "How to verify the change"
    }}
  ],
  "risks": ["risk or caveat"],
  "confidence": 0.0
}}

The status should be either "ready" or "needs_review". The confidence should be between 0 and 1.
"""
