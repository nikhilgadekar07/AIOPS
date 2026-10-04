import sys

sys.path.insert(0, "ai-agents")

from agents.ambiguity_agent import detect_ambiguities

questions = detect_ambiguities(
    title="Cancel order",
    description="Allow users to cancel a pending order",
)
print(questions)
