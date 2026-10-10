SYSTEM = (
    "You are a software impact analyst. Review the spec and the available repo context, "
    "then identify which code paths, files, and components are likely affected and how "
    "confident you are that those impact areas are correct."
)

TEMPLATE = """Requirement title: {title}
Requirement description: {description}

Spec being analyzed:
{spec_json}

Relevant existing codebase context:
{codebase_context}

Return ONLY JSON in this exact shape, with no extra text:
{{
  "impact_analysis": [
    {{
      "component": "...",
      "files": ["..."],
      "reason": "..."
    }}
  ],
  "function_confidence": [
    {{
      "function": "...",
      "confidence": 0.0,
      "reason": "..."
    }}
  ]
}}

"impact_analysis" should identify the most likely files or components that would change.
"function_confidence" should list the functions or APIs whose implementation confidence is highest or lowest.
"confidence" values must stay between 0 and 1.
"""
