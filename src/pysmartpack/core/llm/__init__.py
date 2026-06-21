"""Optional LLM advisor.

Off by default. When disabled (or on any error / timeout) the system falls back
to a deterministic rule-based advisor, so packaging never depends on network or
API keys. Providers are implemented over stdlib HTTP (``urllib``) to avoid hard
third-party SDK dependencies.
"""
from .advisor import get_advice, rule_based_advice, llm_advice  # noqa: F401
