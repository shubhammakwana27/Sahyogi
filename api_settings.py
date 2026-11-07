"""Initial-administrator API controls; credentials are never patient records."""
from app import layout,e,field,form
from access_control import AccessDenied
from agent_settings import api_timeout_seconds
from care_views import select,title
from runtime_settings import PROVIDER_TITLES
from ui_components import panel


def require_api_admin(accounts,user_id):
    user=accounts.user(user_id)
    if user['role']!='coordinator' or not user['is_admin'] or user['must_change']:
        raise AccessDenied('Only the initial coordinator administrator can manage API settings.')
    return user


def api_settings_page(server,csrf,user):
    require_api_admin(server.accounts,user['id']);data=server.api_settings.public()
    try:wait=data['timeout_seconds'] or api_timeout_seconds(data['provider'])
    except ValueError:wait=60 if data['provider']=='sarvam' else 20
    model=data['model'] or ('sarvam-105b' if data['provider']=='sarvam' else '')
    hidden='<input type="hidden" name="settings_version" value="'+str(data['revision'])+'">'
    fields=hidden+select('mode','How should agents run?',{'crewai':'Live AI — uses your API key','demo':'Offline practice — fixed sample rules'},selected='demo' if data['mode']=='demo' else 'crewai')
    fields+=select('provider','API provider',PROVIDER_TITLES,selected=data['provider'])+field('model','Model ID',model,required=False,maximum=120)
    fields+='<label>New API key<input type="password" name="api_key" autocomplete="off" spellcheck="false" maxlength="1024"></label>'
    fields+=field('timeout_seconds','API wait in seconds (10 to 120)',str(wait),kind='number',maximum=3)
    visible='<p><strong>Key status:</strong> '+('A key is set.' if data['key_set'] else 'No active key is set.')+'</p><p class="meta-line">Key entered here stays in memory until the app stops. Live calls can use API credits.</p>'
    body=title('API settings','Initial coordinator administrator only')+'<div class="two-col">'
    body+=panel('Connection settings',visible+form(csrf,'/api-settings/apply',fields+'<button>Apply settings for this app session</button>'),'blue','These settings are shared by all three roles for new requests in this running app. The key is not saved to the database, history or settings file. On restart the app uses startup settings again. Paste the selected provider’s key. Leave blank to keep the current key for the same provider. Existing keys are never shown.')
    tests='<p role="status">'+e(data['last_test'])+'</p><p>This test can use API credits. It uses a made-up document question, with no patient case.</p>'+form(csrf,'/api-settings/test',hidden+'<button>Test current key</button>')
    tests+='<hr class="divider"><h3>Remove the active key</h3>'+form(csrf,'/api-settings/forget',hidden+'<button class="secondary">Remove active key</button>')
    body+=panel('Test or remove the key',tests,'sage','Apply first, then test. The test calls only the Reader and never approves anything. After success, assigned clinical team open the request’s Messages and retry a failed Reader, or Barrier to retry Agent 2. Removing a key affects new requests; already-running requests may finish with their original settings.')+'</div>'
    return layout('API settings',body)
