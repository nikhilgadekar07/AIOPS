SYSTEM = "You are a senior software engineer writing a technical specification before implementation."

TEMPLATE = """Requirement title: {title}
Requirement description: {description}

Resolved decisions (answers to earlier clarifying questions):
{resolved}

Produce a structured technical specification for this requirement.

Respond ONLY with JSON in this exact shape, no other text:
{{
  "functional_requirements": ["..."],
  "non_functional_requirements": ["..."],
  "api_changes": ["..."],
  "risks": ["..."],
  "confidence": 0.0
}}

"confidence" must be a number between 0 and 1 reflecting how certain you are
this spec is correct and complete.
"""