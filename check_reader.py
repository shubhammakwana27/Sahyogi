"""Safe setup checks and optional tests of a selected CrewAI agent.

No database is opened. Never print environment values, raw errors or API keys.
The optional tests can make billable provider requests through the selected agents.
"""
import argparse
import getpass
from contextlib import redirect_stderr, redirect_stdout
from importlib.metadata import PackageNotFoundError, version
import logging
import os
import sys

from agent import provider_settings, read_reply
from agent_settings import api_timeout_seconds
from care_agents import run_care_agent
from reader_errors import safe_error_summary

SAMPLE = "Where should we go? Which documents are needed?"
CARE_SAMPLE = "Which documents do we need for palliative care?"


def synthetic_payload(kind):
    if kind=='barrier':
        return {'scope':'Palliative care administrative assistance',
                'reader_category':'DOCUMENTS_ROUTE','reader_summary':'A made up family asks which documents are needed.',
                'messages':[CARE_SAMPLE],'medicine_status':'NOT_CHECKED','document_status':'NOT_CHECKED'}
    return {'scope':'Administrative palliative care follow-up only',
            'confirmed_barrier':{'code':'DOCUMENTS','description':'Fictional clinical team-confirmed document question for a diagnostic test.'},
            'medicine_status':'NOT_CHECKED','document_status':'NOT_CHECKED',
            'checked_plan_reference':'','checked_document_details':'','care_team_review_open':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Run the selected real agent on fixed synthetic input; API use may be billed")
    parser.add_argument('--agent',choices=['reader','barrier','followup','all'],default='reader',
                        help='Choose an agent to test. all tests each role separately, using only made up inputs.')
    parser.add_argument('--provider',choices=['openai','gemini','sarvam'],help='Temporarily choose the provider for this check')
    parser.add_argument('--prompt-key',action='store_true',help='Enter the key privately for this test, without saving it')
    args = parser.parse_args(argv)
    if args.prompt_key and not args.test:parser.error('--prompt-key requires --test')
    saved={}
    def temporary(name,value):
        if name not in saved:saved[name]=os.environ.get(name)
        os.environ[name]=value
    try:
        if args.provider:temporary('SAHYOGI_PROVIDER',args.provider)
        if args.prompt_key:
            provider,names=provider_settings()
            if not names:print('Choose a supported provider first.');return 2
            key=getpass.getpass('Enter the '+provider+' API key (hidden; not saved): ').strip()
            if not key or key.startswith('YOUR_'):print('A real key is needed for this test.');return 2
            temporary(names[0],key)
            if provider=='sarvam' and not os.getenv(names[1],'').strip():temporary(names[1],'sarvam-105b')
        return run_checks(args)
    except (KeyboardInterrupt,EOFError):
        print('Check stopped. No case record was changed.');return 2
    finally:
        for name,value in saved.items():
            if value is None:os.environ.pop(name,None)
            else:os.environ[name]=value


def run_checks(args):
    print("SAHYOGI reader check")
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    for package in ("crewai", "openai", "google-genai", "pydantic"):
        try:
            print(f"{package}: {version(package)}")
        except PackageNotFoundError:
            print(f"{package}: not installed")
    provider, names = provider_settings()
    print("Provider: " + (provider if names else "invalid"))
    for name in names:
        value = os.getenv(name, "").strip()
        state = "missing" if not value else "placeholder" if value in {"YOUR_API_KEY", "YOUR_OPENAI_API_KEY", "YOUR_GEMINI_API_KEY", "YOUR_SARVAM_API_KEY", "YOUR_SUPPORTED_MODEL_ID", "YOUR_MODEL_ID", "YOUR_GEMINI_MODEL_ID", "YOUR_SARVAM_MODEL_ID"} else "set (value hidden)"
        print(f"{name}: {state}")
    try:
        wait=api_timeout_seconds(provider)
        print(f'API network timeout: {wait} seconds per operation (not a total workflow deadline).')
    except ValueError as error:
        print(safe_error_summary(error));return 2
    if not args.test:
        print("No API request made. Example: check_reader.py --test --agent barrier.")
        return 0
    stages=['reader','barrier','followup'] if args.agent=='all' else [args.agent]
    print('Testing '+', '.join(stages)+' with fixed made up inputs. API use may be billed.')
    print('No case database is opened. A successful test does not change or approve a saved request.')
    old_mode, old_logging = os.environ.get("SAHYOGI_READER"), logging.root.manager.disable
    outcomes=[]
    try:
        os.environ["SAHYOGI_READER"] = "crewai"
        for stage in stages:
            failure=''
            # Framework errors can contain provider payloads. Keep the output fixed and safe.
            with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
                logging.disable(logging.CRITICAL)
                try:result=read_reply(SAMPLE) if stage=='reader' else run_care_agent(stage,synthetic_payload(stage))
                except Exception as error:failure=safe_error_summary(error,component=stage)
            logging.disable(old_logging)
            print('Agent: '+{'reader':'Reader','barrier':'Barrier Assistant','followup':'Follow-up Agent'}[stage])
            if failure or result.engine!='crewai':
                print('Result: FAILED')
                print(failure or (result.summary if stage=='reader' else result.error))
                outcomes.append(2);continue
            print('Result: CrewAI returned a validated '+('reply.' if stage=='reader' else 'draft.'))
            if stage=='reader':
                print(f'Category: {result.category}')
                print('Expected for this sample: DOCUMENTS_ROUTE. No case records were changed.')
                outcomes.append(0 if result.category=='DOCUMENTS_ROUTE' else 3)
            elif stage=='barrier':
                codes=[item['code'] for item in result.output['barriers']]
                print('Barrier codes: '+', '.join(codes))
                print('Expected for this sample: DOCUMENTS. Clinical team confirmation is still required.')
                outcomes.append(0 if 'DOCUMENTS' in codes and not result.output['clinical_concern'] and not result.output['uncertain'] else 3)
            else:
                print('Administrative draft only. Clinical team approval is still required.')
                outcomes.append(0)
    finally:
        logging.disable(old_logging)
        if old_mode is None:
            os.environ.pop("SAHYOGI_READER", None)
        else:
            os.environ["SAHYOGI_READER"] = old_mode
    return 2 if 2 in outcomes else 3 if 3 in outcomes else 0


if __name__ == "__main__":
    raise SystemExit(main())
