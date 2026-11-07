"""Per-server, memory-only provider settings with immutable per-request snapshots."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass,field,replace
import os
import re
from threading import Lock

PROVIDER_NAMES={'openai':('OPENAI_API_KEY','OPENAI_MODEL'),
                'sarvam':('SARVAM_API_KEY','SARVAM_MODEL'),
                'gemini':('GEMINI_API_KEY','GEMINI_MODEL')}
PROVIDER_TITLES={'sarvam':'Sarvam AI','gemini':'Google Gemini','openai':'OpenAI'}
ACTIVE_SETTINGS=ContextVar('sahyogi_api_settings',default=None)


@dataclass(frozen=True)
class ProviderConfig:
    provider:str
    model:str
    api_key:str=field(repr=False)
    mode:str='crewai'
    timeout_seconds:int|None=None
    revision:int=0
    source:str='Startup settings'


def environment_settings():
    provider=os.getenv('SAHYOGI_PROVIDER','openai').strip().lower()
    names=PROVIDER_NAMES.get(provider,('',''))
    return ProviderConfig(provider,os.getenv(names[1],'').strip(),os.getenv(names[0],'').strip(),
                          os.getenv('SAHYOGI_READER','crewai').strip().lower())


def current_settings():
    return ACTIVE_SETTINGS.get() or environment_settings()


@contextmanager
def settings_context(config):
    token=ACTIVE_SETTINGS.set(config)
    try:yield config
    finally:ACTIVE_SETTINGS.reset(token)


class RuntimeSettings:
    def __init__(self):
        self._lock=Lock();self._config=None;self._revision=0
        self._last_test='No connection test has been run for these settings.'
        self._test_tokens={};self._test_busy=False

    def snapshot(self):
        with self._lock:return self._config or replace(environment_settings(),revision=self._revision)

    def public(self):
        with self._lock:
            config=self._config or replace(environment_settings(),revision=self._revision)
            return {'provider':config.provider,'model':config.model,'mode':config.mode,
                    'key_set':bool(config.api_key) and not config.api_key.startswith('YOUR_'),
                    'timeout_seconds':config.timeout_seconds,'revision':config.revision,
                    'source':config.source,'last_test':self._last_test}

    def _check_version(self,version):
        if str(version)!=str(self._revision):raise ValueError('API settings changed. Reload this page before continuing.')

    def apply(self,data):
        provider=data.get('provider','');mode=data.get('mode','')
        if provider not in PROVIDER_NAMES:raise ValueError('Choose a listed API provider.')
        if mode not in {'demo','crewai'}:raise ValueError('Choose Live AI or Offline practice.')
        model=data.get('model','').strip()
        if (mode=='crewai' and not model) or (model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}',model)):
            raise ValueError('Enter a valid model ID, using at most 120 characters.')
        if '/' in model and not model.startswith(provider+'/'):raise ValueError('The model prefix must match the selected provider.')
        key=data.get('api_key','').strip()
        if key and (len(key)>1024 or key.startswith('YOUR_') or any(not 33<=ord(c)<=126 for c in key)):
            raise ValueError('Enter a real API key without spaces or line breaks.')
        try:timeout=int(data.get('timeout_seconds',''))
        except ValueError:raise ValueError('Choose an API wait between 10 and 120 seconds.') from None
        if not 10<=timeout<=120:raise ValueError('Choose an API wait between 10 and 120 seconds.')
        with self._lock:
            self._check_version(data.get('settings_version'))
            previous=self._config or environment_settings()
            if not key and previous.provider==provider:key=previous.api_key
            if mode=='crewai' and (not key or key.startswith('YOUR_')):
                raise ValueError('Enter a key for the selected provider. The key is not saved to disk.')
            self._revision+=1
            self._config=ProviderConfig(provider,model,key,mode,timeout,self._revision,'Entered in this app session')
            self._last_test='Settings applied. Test the current key before retrying a failed request.'

    def forget(self,version):
        with self._lock:
            self._check_version(version)
            config=self._config or environment_settings();self._revision+=1
            self._config=replace(config,api_key='',revision=self._revision,source='Active key removed')
            self._last_test='Active key removed. Enter a key or use Offline practice.'

    def test(self,version,token,reader=None):
        # No database or patient message is passed into this connection check.
        from agent import read_reply
        from reader_errors import MESSAGES,classify_error
        if not re.fullmatch(r'[a-f0-9]{32}',token or ''):raise ValueError('Reload the API settings page before testing.')
        with self._lock:
            self._check_version(version)
            if token in self._test_tokens:return
            if self._test_busy:raise ValueError('A connection test is already running. Reload in a moment.')
            config=self._config or replace(environment_settings(),revision=self._revision)
            if config.mode=='demo' or not config.api_key or not config.model:
                raise ValueError('Apply Live AI settings with a key and model before testing.')
            self._test_tokens[token]=True;self._test_busy=True
        try:
            with settings_context(config):
                result=(reader or read_reply)('Which documents do we need for palliative care?')
            if result.engine=='crewai':
                message='Connection test succeeded: the Reader returned a validated answer. No saved request was changed or approved.'
            else:
                match=re.match(r'^\[([A-Z_]+)\]',result.summary)
                code=match.group(1) if match and match.group(1) in MESSAGES else 'UNKNOWN'
                message='Connection test failed. ['+code+'] '+MESSAGES[code]
        except Exception as error:
            code=classify_error(error);message='Connection test failed. ['+code+'] '+MESSAGES[code]
        finally:
            with self._lock:self._test_busy=False
        with self._lock:
            if config.revision==self._revision:self._last_test=message
            if len(self._test_tokens)>50:self._test_tokens={token:True}
