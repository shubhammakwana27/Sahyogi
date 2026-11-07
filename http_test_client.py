"""Test-only HTTP client. Authentication still goes through the actual login form."""
import http.client
from html.parser import HTMLParser
from urllib.parse import urlencode

TEST_PASSWORD='Testpass123!'
NEW_PASSWORD='Newpass456!'


class Forms(HTMLParser):
    def __init__(self):super().__init__();self.forms=[];self.current=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='form':self.current={'action':a.get('action'),'hidden':{}}
        elif tag=='input' and self.current is not None and a.get('type')=='hidden':self.current['hidden'][a.get('name')]=a.get('value','')
    def handle_endtag(self,tag):
        if tag=='form' and self.current is not None:self.forms.append(self.current);self.current=None


class Browser:
    def __init__(self,server):self.server=server;self.cookie='';self.csrf=''
    def request(self,method,path,data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        h={'Content-Type':'application/x-www-form-urlencoded'}
        # Native browser forms include an Origin header on POST. Exercise that
        # path for all authenticated forms, rather than only testing its absence.
        if method.upper()=='POST':h['Origin']=f'http://127.0.0.1:{self.server.server_port}'
        if self.cookie:h['Cookie']=self.cookie
        h.update(headers or {})
        conn.request(method,path,urlencode(data) if data is not None else None,h)
        r=conn.getresponse();head=dict(r.getheaders());body=r.read().decode();status=r.status;conn.close()
        if 'Set-Cookie' in head:self.cookie=head['Set-Cookie'].split(';')[0]
        parser=Forms();parser.feed(body)
        for f in parser.forms:
            if 'csrf' in f['hidden']:self.csrf=f['hidden']['csrf'];break
        return status,head,body
    def post(self,path,data=None):return self.request('POST',path,{'csrf':self.csrf,**(data or {})})
    def login(self,name,password,new_password=None):
        assert self.request('GET','/login')[0]==200
        status,head,body=self.post('/login',{'username':name,'password':password})
        assert status==303,body
        status,_,body=self.request('GET',head['Location']);assert status==200,body
        if head['Location']=='/password' and new_password:
            status,head,body=self.post('/password',{'current':password,'new':new_password,'repeat':new_password});assert status==303,body
            assert self.request('GET',head['Location'])[0]==200
        return self


def coordinator_browser(server):
    accounts=server.accounts
    user=accounts.create_user('testcoord','Anita','coordinator',TEST_PASSWORD,bootstrap=True)
    browser=Browser(server).login('testcoord',TEST_PASSWORD)
    browser.user_id=user
    server.csrf=browser.csrf  # compatibility with older tests constructing form dictionaries
    return browser


def staff_browser(server,coordinator,case_id):
    accounts=server.accounts
    user=accounts.create_user('teststaff','Test clinical team','staff',TEST_PASSWORD,creator=coordinator.user_id)
    accounts.change_password(user,TEST_PASSWORD,NEW_PASSWORD)
    accounts.assign(case_id,'teststaff',coordinator.user_id,server.store.detail(case_id)['version'])
    return Browser(server).login('teststaff',NEW_PASSWORD)
