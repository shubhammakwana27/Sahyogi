"""Conservative text screens, independent of every LLM. Not a triage assessment."""
import re
import unicodedata

URGENT_NOTICE=('Possible urgent clinical concern. Seek urgent medical help now through your treating team '
               'or local emergency service. Do not wait for a reply in this app.')


def norm(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text).casefold()).strip()


def urgent_hint(text):
    value=norm(text)
    terms=('breathing very slowly','breathing slowly','slow breathing','barely waking',
           'barely wakes','not waking','cannot wake','can\'t wake','unresponsive',
           'unconscious','severe breathlessness','struggling to breathe','not breathing',
           'श्वास खूप हळू','श्वास हळू','शुद्ध नाही','जागे होत नाही','बेशुद्ध',
           'सांस बहुत धीमी','साँस बहुत धीमी','सांस धीमी','बेहोश','जाग नहीं')
    return any(term in value for term in terms)


def clinical_screen(text):
    value=norm(text)
    # A medicine's name/indication alone is not a symptom report.
    for phrase in ('pain medicine','pain medication','pain relief','pain tablets',
                   'दर्द की दवा','दर्दकी दवा','दर्दकीदवा','वेदनाशामक'):
        value=value.replace(phrase,'medicine')
    terms=('pain','dose','symptom','vomit','breath','bleed','fever','sleepy','drowsy',
           'constipat','stools','addict','scared to take','afraid to take','too weak',
           'last stage','doesn\'t want to go to the hospital','does not want to go to the hospital',
           'वेदना','दुख','दर्द','श्वास','उलटी','ताप','डोस','खुराक','नींद','न ींद',
           'झोप','आराम नाही','unresponsive','barely waking')
    return urgent_hint(text) or any(term in value for term in terms)
