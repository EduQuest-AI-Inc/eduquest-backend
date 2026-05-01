import sys

# Remove bots mocks so tests in this directory import the real bots package.
# The root conftest mocks bots.* globally; we undo that here so BotProvider
# and its helpers can be tested with real imports.
# The agents SDK mock (sys.modules['agents']) stays in place — GradingInput is
# a pure Pydantic model that doesn't depend on the SDK at construction time.
for key in [k for k in sys.modules if k == "bots" or k.startswith("bots.")]:
    sys.modules.pop(key, None)
