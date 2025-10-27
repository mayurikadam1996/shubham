# app/guardrails.py
from typing import Optional
import re
from adk import callbacks as cb
from adk.types import CallbackContext, ModelRequest, ModelResponse, ToolCall, ToolResult

JAILBREAK_PATTERNS = re.compile(
    r"(ignore (all )?(previous|prior) (instructions|rules)|"
    r"simulate (developer|dev)_?mode|"
    r"reveal( the)? system prompt|"
    r"disable (safety|guardrails)|"
    r"act as .* with no restrictions)",
    re.IGNORECASE,
)

TOXIC_HINT = re.compile(r"(kill|hate|self[-\s]?harm|violence)", re.IGNORECASE)
PII_HINT = re.compile(r"\b(\d{12,16}|\d{3}-\d{2}-\d{4})\b")  # simplistic example

def _safe_block_msg(reason: str) -> str:
    return (
        f"⚠️ I can’t proceed: {reason}. "
        "You can ask about provider details (NPI, TIN, CPT, specialty, location), "
        "but I won’t bypass safety or reveal hidden instructions."
    )

def _is_numeric_len(s: str, n: int) -> bool:
    return s.isdigit() and len(s) == n

def _validate_tool_inputs(tool: ToolCall) -> Optional[str]:
    # Allowlist tools that can touch data
    allowed = {"PsxProviderSearchTool", "PsxProviderSearchService", "ProviderSearchTool"}
    if tool.name not in allowed:
        return f"Tool '{tool.name}' is not allowed."

    # Common numeric fields guardrails (adjust to your DTO)
    payload = tool.arguments or {}
    npi = str(payload.get("npi", "")).strip()
    tin = str(payload.get("tin", "")).strip()
    cpt = str(payload.get("cpt", "")).strip()

    if npi and not _is_numeric_len(npi, 10):
        return "Invalid NPI: must be a 10-digit numeric string."
    if tin and not _is_numeric_len(tin, 9):
        return "Invalid TIN: must be a 9-digit numeric string."
    if cpt and not (_is_numeric_len(cpt, 5) and not (payload.get("zip") == cpt)):
        # light CPT vs ZIP confusion guard – you can force user confirm if ambiguous
        payload["needs_disambiguation"] = True

    # Optional: add query length limits, sort/limit caps, and field allowlists here.
    return None

class GuardrailCallbacks(
    cb.BeforeAgentCallback,
    cb.BeforeModelCallback,
    cb.AfterModelCallback,
    cb.BeforeToolCallback,
    cb.AfterToolCallback,
    cb.OnErrorCallback,
):
    # Run-level checks
    def before_agent(self, ctx: CallbackContext):
        # e.g., stop runaway loops
        if ctx.run_stats.model_invocations > 50:
            ctx.block(_safe_block_msg("run limit exceeded"))
        # Optionally gate by tenant/user policy in ctx.state

    # Prompt guardrails (before hitting LLM)
    def before_model(self, ctx: CallbackContext, req: ModelRequest):
        text = (req.messages[-1].content if req.messages else "") or ""
        if JAILBREAK_PATTERNS.search(text):
            ctx.block(_safe_block_msg("detected jailbreak / prompt-injection"))
        if TOXIC_HINT.search(text):
            ctx.block(_safe_block_msg("toxic or harmful request"))
        if PII_HINT.search(text):
            ctx.block(_safe_block_msg("possible PII in user input"))
        # You can also sanitize: strip hidden XML/Markdown blocks, URLs, emails, etc.

    # Output guardrails (post LLM)
    def after_model(self, ctx: CallbackContext, res: ModelResponse):
        out = res.text or ""
        if TOXIC_HINT.search(out):
            ctx.replace_output("I can’t share that content. Ask something else about providers.")
        if "BEGIN_SYSTEM_PROMPT" in out or "api_key" in out:
            ctx.replace_output("I can’t reveal internal instructions or secrets.")

    # Tool call guardrails
    def before_tool(self, ctx: CallbackContext, call: ToolCall):
        err = _validate_tool_inputs(call)
        if err:
            ctx.block(_safe_block_msg(err))

    def after_tool(self, ctx: CallbackContext, result: ToolResult):
        # Optionally scrub PII from tool results before the model sees them
        if isinstance(result.output, str) and PII_HINT.search(result.output):
            result.output = re.sub(PII_HINT, "[REDACTED]", result.output)

    # Safe error messages
    def on_error(self, ctx: CallbackContext, error: Exception):
        ctx.replace_output("Something went wrong. I’ve logged it internally without exposing details.")
