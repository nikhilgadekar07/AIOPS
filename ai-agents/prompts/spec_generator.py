SYSTEM = ("You are a senior software engineer writing a technical specification "
          "before implementation. Be concrete and specific, not generic. When "
          "existing codebase context is provided, ground your spec in it -- "
          "reference real file names, function names, and patterns you see, "
          "rather than inventing generic ones.")

TEMPLATE = """Requirement title: {title}
Requirement description: {description}

Resolved decisions (answers to earlier clarifying questions):
{resolved}

{feedback_section}

Relevant existing codebase context (retrieved from the actual repository):
{codebase_context}

Produce a structured technical specification for this requirement.

Respond ONLY with JSON in this exact shape, no other text:
{{
  "functional_requirements": ["..."],
  "non_functional_requirements": ["..."],
  "affected_components": ["..."],
  "api_changes": ["..."],
  "database_changes": ["..."],
  "test_requirements": ["..."],
  "risks": ["..."],
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
  ],
  "confidence": 0.0,
  "review_status": "moderate confidence"
}}

"confidence" must be a number between 0 and 1 reflecting how certain you are
this spec is correct and complete given what you know. If codebase context
was provided and it's thin or seems unrelated to the requirement, lower your
confidence rather than guessing.
"review_status" should be a brief label: "high confidence", "moderate confidence",
or "needs careful review". If you are not confident, choose "needs careful review".
"impact_analysis" should identify the likely modules/files touched by the change.
"function_confidence" should give confidence per API or function that is likely involved.
"""