"""Bounded API wait settings shared by the three agents and safe diagnostics."""
import os

from reader_errors import ReaderConfigurationError
from runtime_settings import ACTIVE_SETTINGS


def api_timeout_seconds(provider=None):
    active=ACTIVE_SETTINGS.get()
    if active is not None and active.timeout_seconds is not None and (provider is None or provider==active.provider):
        return active.timeout_seconds
    provider=provider or os.getenv('SAHYOGI_PROVIDER','openai').strip().lower()
    raw=os.getenv('SAHYOGI_API_TIMEOUT_SECONDS','').strip()
    if not raw:return 60 if provider=='sarvam' else 20
    try:value=int(raw)
    except ValueError:raise ReaderConfigurationError('Invalid API timeout') from None
    if not 10<=value<=120:raise ReaderConfigurationError('API timeout outside the supported range')
    return value


def agent_execution_seconds(llm):
    # Leave time for parsing after the configured SDK request wait. The SDK
    # timeout is a network-operation limit, not a total end-to-end deadline.
    timeout=getattr(llm,'timeout',None)
    if not isinstance(timeout,(int,float)):timeout=api_timeout_seconds()
    return max(45,timeout+15)
