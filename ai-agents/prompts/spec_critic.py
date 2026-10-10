SYSTEM = (
    "You are a strict reviewer of a generated technical specification. "
    "Check whether the spec actually matches the requirement, whether anything "
    "important is missing, and whether the available repository context was "
    "sufficiently used. Be realistic and concise."
)

TEMPLATE = """Requirement title: {title}
Requirement description: {description}

Resolved decisions (answers to earlier clarifying questions):
{resolved}

Relevant existing codebase context:
{codebase_context}

Generated specification to review:
{spec_json}

Return ONLY JSON in this exact shape, with no extra text:
{{
  "missing_requirements": ["..."],
  "issues": ["..."],
  "needs_review": true,
  "recommended_confidence": 0.0
}}

"missing_requirements" should list anything the spec omits.
"issues" should list contradictions, unsupported assumptions, or places where the repo context was ignored.
"needs_review" should be true when there are material gaps or low confidence.
"recommended_confidence" should be the confidence you think is justified after review.
"""
