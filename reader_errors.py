"""Safe, fixed reader diagnostics. Never display raw exception messages or bodies."""


class ReaderOutputError(ValueError):
    """The crew finished without the required validated reply object."""


class ReaderConfigurationError(ValueError):
    """Invalid local agent settings; no provider request should be made."""


MESSAGES = {
    "CONFIG": "Check the model/provider combination and SAHYOGI_API_TIMEOUT_SECONDS (10 to 120), then restart.",
    "AUTH": "The API key was rejected. Ask the initial coordinator to replace it under API settings, then test and retry.",
    "ACCESS": "API access was denied. Check the key, project and model permissions.",
    "MODEL": "The requested API resource was not found. Check the exact model ID, project access and API endpoint.",
    "CREDITS": "API credits or quota are exhausted. Check the API project's billing and usage limits.",
    "SPEND_LIMIT": "An API spending or usage limit was reached. Check the project and organisation limits.",
    "RATE_LIMIT": "The API rate limit was reached. Wait before trying again.",
    "TIMEOUT": "The AI request took too long. Check the connection and API wait setting, then try again later.",
    "CONNECTION": "The API could not be reached. Check the connection, proxy, firewall and certificates.",
    "REQUEST": "The API rejected the request format or settings. Check package versions and model compatibility.",
    "DEPENDENCY": "CrewAI dependencies could not load. Install requirements.txt using the app's Python environment.",
    "OUTPUT": "The AI returned an empty, incomplete or invalid structured answer. Clinical team must review the original message.",
    "SERVICE": "The API service could not complete the request. Wait and try again later.",
    "UNKNOWN": "The agent failed for an unclassified reason. Run check_reader.py --test with the matching --agent option for a separate check.",
}


def classify_error(error):
    """Read only allowlisted error codes and types, including wrapped SDK errors."""
    errors, pending, seen = [], [error], set()
    while pending and len(errors) < 20:
        item = pending.pop()
        if not isinstance(item, BaseException) or id(item) in seen:
            continue
        seen.add(id(item))
        errors.append(item)
        pending.extend([item.__context__, item.__cause__])
        nested=getattr(item,'exceptions',())
        if isinstance(nested,tuple):pending.extend(nested)
    # Prefer the underlying provider status to a wrapper such as ConnectionError.
    for item in reversed(errors):
        code = getattr(item, "code", None)
        body = getattr(item, "body", None)
        if body is None:
            body = getattr(item, "response_json", None)
        if isinstance(body, dict):
            info = body.get("error", body)
            if isinstance(info, dict):
                code = info.get("code") or code
                if info.get("type") == "invalid_api_key_error":
                    return "AUTH"  # Sarvam reports key rejection as HTTP 403.
        if code == "invalid_api_key_error":
            return "AUTH"
        if code in ("insufficient_quota", "insufficient_quota_error", "credit_balance_exhausted", "billing_hard_limit_reached"):
            return "CREDITS"
        if code in ("project_spend_limit_exceeded", "organization_spend_limit_exceeded",
                    "organization_usage_limit_exceeded", "seat_budget_exhausted_error"):
            return "SPEND_LIMIT"
        if code in ("rate_limit_exceeded_error", "model_rate_limit_exceeded_error"):
            return "RATE_LIMIT"
        status = getattr(item, "status_code", None)
        if status is None and isinstance(getattr(item, "code", None), int):
            status = item.code  # Google Gen AI APIError exposes HTTP status as code.
        if status == 401:
            return "AUTH"
        if status == 402:
            return "CREDITS"
        if status == 403:
            return "ACCESS"
        if status == 404:
            return "MODEL"
        if status == 429:
            return "RATE_LIMIT"
        if status == 408:
            return "TIMEOUT"
        if status in (400, 422):
            return "REQUEST"
        if isinstance(status, int) and 500 <= status <= 599:
            return "SERVICE"
    for item in reversed(errors):
        names = {cls.__name__ for cls in type(item).__mro__}
        if isinstance(item,ReaderConfigurationError):
            return 'CONFIG'
        if isinstance(item, TimeoutError) or names.intersection({"APITimeoutError", "TimeoutException", "TimeoutExpired"}):
            return "TIMEOUT"
        if isinstance(item, ImportError):
            return "DEPENDENCY"
        if isinstance(item, ReaderOutputError) or names.intersection({"ValidationError", "JSONDecodeError", "LengthFinishReasonError", "ContentFilterFinishReasonError", "OutputParserError"}):
            return "OUTPUT"
        # Match only CrewAI's fixed internal empty-response message, never
        # expose arbitrary exception strings or provider response bodies.
        if isinstance(item,ValueError) and item.args==('Invalid response from LLM call - None or empty.',):
            return 'OUTPUT'
        if isinstance(item, ConnectionError) or names.intersection({"APIConnectionError", "NetworkError", "ProtocolError", "ConnectError"}):
            return "CONNECTION"
    return "UNKNOWN"


def safe_error_summary(error, *, component='reader'):
    code = classify_error(error)
    name={'reader':'Reader','barrier':'Barrier Assistant','followup':'Follow-up Agent'}.get(component,'AI agent')
    return f"[{code}] {name}: {MESSAGES[code]} Clinical team review is required."
