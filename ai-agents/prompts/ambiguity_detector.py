SYSTEM = "You are a senior software analyst reviewing feature requirements before implementation."

TEMPLATE = """Requirement title: {title}
Requirement description: {description}

Identify ambiguities in this requirement that would affect implementation.
For each ambiguity, propose a reasonable default assumption.
If there are no meaningful ambiguities, return an empty list.

Respond ONLY with JSON in this exact shape, no other text:
{{
  "questions": [
    {{"question": "...", "assumed_default": "..."}}
  ]
}}
"""