import os

# None means "use the OpenAI Agents SDK default model". Set AAA_MODEL to pin one.
MODEL = os.environ.get("AAA_MODEL") or None
