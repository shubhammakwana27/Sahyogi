"""Small accessible presentation helpers. Pages use no JavaScript or external assets,
so that the strict Content-Security-Policy in portal.py can stay as it is."""
from html import escape


def esc(value):return escape(str(value),quote=True)


def help_button(title,text):
    return '<details class="context-help"><summary aria-label="Help for '+esc(title)+'" title="Help">?</summary><div class="help-popover"><strong>'+esc(title)+'</strong><p>'+esc(text)+'</p></div></details>'


def panel(title,body,tone='',help_text='',id=''):
    """tone only matters for 'primary' (the next action) and 'red'; other values render plain."""
    return '<section class="card tone-'+esc(tone or 'plain')+'"'+(' id="'+esc(id)+'"' if id else '')+'><div class="card-head"><h2>'+esc(title)+'</h2>'+(help_button(title,help_text) if help_text else '')+'</div>'+body+'</section>'


def pill(text,tone='neutral'):
    return '<span class="pill pill-'+esc(tone)+'">'+esc(text)+'</span>'


def link(label,url,secondary=False):
    return '<a class="button-link'+(' secondary-link' if secondary else '')+'" href="'+esc(url)+'">'+esc(label)+'</a>'


def facts(rows):
    """A label and value list. Values are HTML the caller has already escaped."""
    return '<dl class="facts">'+''.join('<div><dt>'+esc(k)+'</dt><dd>'+v+'</dd></div>' for k,v in rows)+'</dl>'


ICON_PATHS={
 'inbox':'<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5.5 5h13L21 13v6H3v-6z"/>',
 'plus':'<path d="M12 5v14M5 12h14"/>',
 'chat':'<path d="M4 5h16v11H9l-5 4z"/>',
 'book':'<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h11"/>',
 'archive':'<path d="M3 5h18v4H3z"/><path d="M5 9v10h14V9M10 13h4"/>',
 'users':'<circle cx="9" cy="8" r="3.5"/><path d="M3 20c.5-4 3-6 6-6s5.5 2 6 6"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.5c1.700.8 2.700 2.700 3 5.5"/>',
 'key':'<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>',
 'menu':'<path d="M4 7h16M4 12h16M4 17h16"/>',
 'lock':'<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
 'check':'<path d="M5 12.5l4.500 4.500L19 7.500"/>',
 'back':'<path d="M14 6l-6 6 6 6"/>',
}


def icon(name):
    return '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+ICON_PATHS[name]+'</svg>'


THEME_CSS='''
:root{color-scheme:light dark;--bg:#f5f5f2;--surface:#fff;--surface-2:#f5f5f2;--ink:#1a1c20;--ink-2:#555a64;--line:#e3e3dd;--line-2:#c9c9c1;
--accent:#2c3f9f;--accent-hover:#222f7e;--on-accent:#fff;--accent-soft:#eef0fb;--accent-line:#cdd3f3;--mark:#2c3f9f;
--ok:#1b6a44;--ok-bg:#e4f3ea;--warn:#7f5200;--warn-bg:#fbf0d8;--warn-line:#ecd6a3;--bad:#a12525;--bad-bg:#fbe9e6;--bad-line:#efc4bd;--shadow:0 8px 28px rgb(20 22 30/.16)}
@media(prefers-color-scheme:dark){:root{--bg:#121316;--surface:#1a1c20;--surface-2:#22252a;--ink:#eceef1;--ink-2:#a5aab4;--line:#2d3036;--line-2:#454951;
--accent:#a3b1ff;--accent-hover:#bcc6ff;--on-accent:#12162e;--accent-soft:#20253f;--accent-line:#39406a;--mark:#3e52b8;
--ok:#7fd3a5;--ok-bg:#16301f;--warn:#e9bf6c;--warn-bg:#33280f;--warn-line:#5a4720;--bad:#f3a196;--bad-bg:#3a1b18;--bad-line:#6a2f28;--shadow:0 8px 28px rgb(0 0 0/.5)}}
html{font-size:15px}html.role-family{font-size:17px}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:1rem/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans","Noto Sans Devanagari",sans-serif;-webkit-font-smoothing:antialiased;overflow-wrap:break-word}
a{color:var(--accent);text-underline-offset:2px}
a,button,input,select,textarea,summary{touch-action:manipulation}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
h1,h2,h3{font-weight:600;letter-spacing:-.01em}
.icon{width:1.15em;height:1.15em;flex:none}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
.muted,.sub,small{color:var(--ink-2)}small{font-size:.84rem}
hr,.divider{border:0;border-top:1px solid var(--line);margin:1.25rem 0}
ol,ul{padding-left:1.3rem}li{margin:.3rem 0}

/* Shell */
.app-shell{display:grid;grid-template-columns:15.75rem minmax(0,1fr);min-height:100vh}
.sidebar{position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column;gap:1.4rem;padding:1.1rem .75rem;border-right:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:.6rem;padding:0 .5rem;color:var(--ink);font-size:1.07rem;font-weight:650;letter-spacing:-.01em;text-decoration:none}
.brand-mark{display:grid;place-items:center;width:1.75rem;height:1.75rem;border-radius:.45rem;background:var(--mark);color:#fff;font-size:1.05rem;font-weight:600;line-height:1}
.side-nav{display:grid;gap:1px}
.side-label{margin:0 .6rem .3rem;font-size:.78rem;font-weight:500;color:var(--ink-2)}
.side-nav a{display:flex;align-items:center;gap:.6rem;min-height:2.3rem;padding:.35rem .6rem;border-radius:.45rem;color:var(--ink-2);text-decoration:none}
.side-nav a:hover{background:color-mix(in srgb,var(--ink) 6%,transparent);color:var(--ink)}
.side-nav a[aria-current]{background:var(--surface);color:var(--ink);font-weight:550;box-shadow:0 0 0 1px var(--line)}
.side-account{margin-top:auto;padding:.9rem .5rem 0;border-top:1px solid var(--line);font-size:.9rem}
.side-person{display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;min-width:0}
.avatar{display:grid;place-items:center;flex:none;width:2rem;height:2rem;border-radius:50%;background:var(--accent-soft);color:var(--accent);font-weight:600}
.side-person strong{display:block;font-weight:550;line-height:1.25}.side-person small{display:block}
.side-links{display:flex;align-items:center;justify-content:space-between;gap:.5rem}.side-links a{color:var(--ink-2);font-size:.86rem}
.side-links button{min-height:0;margin:0;padding:.2rem 0;border:0;background:none;color:var(--ink-2);font-size:.86rem;font-weight:400;text-decoration:underline;text-underline-offset:2px}
.side-links button:hover{background:none;color:var(--ink)}
.app-main{width:100%;max-width:1180px;margin:0 auto;padding:.9rem 2.25rem 4rem;min-width:0}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:.9rem;min-height:2.2rem;margin-bottom:1.4rem}
.topbar .brand{display:none;padding:0}
.topbar-title{font-size:.84rem;color:var(--ink-2)}
.top-actions{display:flex;align-items:center;gap:.6rem}
.top-actions .pill{margin:0}
.tabbar{display:none}

/* Page headers */
.page-title{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin:0 0 1.25rem}
.page-title h1{margin:0;font-size:1.65rem;line-height:1.2;letter-spacing:-.02em}
.page-title p{margin:.3rem 0 0;color:var(--ink-2)}
.page-title .button-link{margin:0}
.back{display:inline-flex;align-items:center;gap:.2rem;margin:0 0 .5rem -.2rem;color:var(--ink-2);font-size:.88rem;text-decoration:none}.back:hover{color:var(--ink)}
.case-title{display:flex;align-items:center;flex-wrap:wrap;gap:.35rem .75rem;margin:0 0 .9rem}
.case-title h1{margin:0;font-size:1.65rem;line-height:1.2;letter-spacing:-.02em}.case-title .pill{margin:0}
.case-meta{display:flex;flex-wrap:wrap;gap:.5rem 2.25rem;margin:0 0 1.4rem;padding:0 0 1.1rem;border-bottom:1px solid var(--line)}
.case-meta dt{font-size:.8rem;color:var(--ink-2)}.case-meta dd{margin:0;font-weight:500}

/* Cards */
.card{position:relative;margin:0 0 1rem;padding:1.2rem 1.3rem;background:var(--surface);border:1px solid var(--line);border-radius:.7rem;min-width:0}
.card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:.75rem;margin-bottom:.7rem}
.card h2{margin:0 0 .6rem;font-size:1.07rem;line-height:1.35}.card-head h2{margin:0}
.card h3{margin:1.1rem 0 .35rem;font-size:1rem}
.card p{margin:.6rem 0}.card>:last-child{margin-bottom:0}
.card .card{padding:0;margin:0;border:0;background:none}
.tone-primary{background:var(--accent-soft);border-color:var(--accent-line)}
.next-text{font-size:1.13rem;line-height:1.4;font-weight:500;margin:0 0 .25rem}
.tone-primary .help-popover{font-weight:400}
.tone-red{background:var(--bad-bg);border-color:var(--bad-line)}
.grid,.two-col{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:1rem;align-items:start}
.split{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:1rem;align-items:start}
.narrow{max-width:620px}
.facts{margin:.75rem 0 0;display:grid;gap:.5rem}.facts dt{font-size:.82rem;color:var(--ink-2)}.facts dd{margin:0}

/* Help */
.context-help{position:relative;flex:none;margin:0}
.context-help summary{list-style:none;display:grid;place-items:center;position:relative;width:1.45rem;height:1.45rem;border:1px solid var(--line-2);border-radius:50%;color:var(--ink-2);font-size:.8rem;font-weight:500;line-height:1;cursor:pointer}
.context-help summary::after{content:"";position:absolute;inset:-.55rem}
.context-help summary::-webkit-details-marker{display:none}
.context-help summary:hover,.context-help[open] summary{background:var(--surface-2);color:var(--ink)}
.help-popover{position:absolute;right:0;top:calc(100% + .4rem);z-index:50;width:min(340px,78vw);padding:.85rem 1rem;background:var(--surface);border:1px solid var(--line);border-radius:.6rem;box-shadow:var(--shadow);color:var(--ink);font-size:.9rem}
.help-popover p{margin:.3rem 0 0;font-size:.9rem}

/* Status */
.pill,.badge{display:inline-flex;align-items:center;margin:0 .3rem .3rem 0;padding:.1rem .5rem;border-radius:.35rem;background:color-mix(in srgb,var(--ink) 7%,transparent);color:var(--ink-2);font-size:.8rem;font-weight:500;line-height:1.5;white-space:nowrap}
.pill-sage{background:var(--ok-bg);color:var(--ok)}.pill-sand{background:var(--warn-bg);color:var(--warn)}.pill-red{background:var(--bad-bg);color:var(--bad)}
.notice,.alert{margin:0 0 1rem;padding:.75rem 1rem;background:var(--surface);border:1px solid var(--line);border-radius:.6rem}
.notice p{margin:0}.notice strong{display:block}
.notice.warn,.alert{background:var(--warn-bg);border-color:var(--warn-line);color:var(--warn)}
.notice.urgent{background:var(--bad-bg);border-color:var(--bad-line);color:var(--bad);font-weight:500}
.card .alert{margin:.75rem 0}

/* Forms */
label{display:block;margin:.9rem 0 .3rem;font-size:.93rem;font-weight:500}
input:not([type=checkbox]),textarea,select{display:block;width:100%;min-height:2.6rem;margin-top:.3rem;padding:.5rem .7rem;font:inherit;font-weight:400;color:var(--ink);background:var(--surface);border:1px solid var(--line-2);border-radius:.45rem}
input:not([type=checkbox]):hover,textarea:hover,select:hover{border-color:var(--ink-2)}
input[readonly]{background:var(--surface-2);color:var(--ink-2)}
textarea{min-height:6.5rem;resize:vertical;line-height:1.5}
select{appearance:none;padding-right:2rem;background-image:linear-gradient(45deg,transparent 50%,var(--ink-2) 50%),linear-gradient(135deg,var(--ink-2) 50%,transparent 50%);background-size:5px 5px;background-position:calc(100% - 1rem) 55%,calc(100% - .7rem) 55%;background-repeat:no-repeat}
label.check{display:flex;align-items:flex-start;gap:.55rem;margin:.75rem 0;font-weight:400}
input[type=checkbox]{flex:none;width:1.15rem;height:1.15rem;margin:.17rem 0 0;accent-color:var(--accent)}
button,.button-link{display:inline-flex;align-items:center;justify-content:center;gap:.4rem;min-height:2.6rem;margin-top:1rem;padding:.45rem 1rem;background:var(--accent);border:1px solid var(--accent);border-radius:.45rem;color:var(--on-accent);font:inherit;font-weight:550;line-height:1.25;text-decoration:none;cursor:pointer;transition:background-color .12s}
button:hover,.button-link:hover{background:var(--accent-hover);border-color:var(--accent-hover)}
.secondary,button.secondary,.secondary-link{background:var(--surface);border-color:var(--line-2);color:var(--ink)}
button.secondary:hover,.secondary-link:hover{background:var(--surface-2);border-color:var(--line-2)}
.button-row{display:flex;flex-wrap:wrap;gap:.6rem}.button-row>*{margin-top:.5rem}
.small-link{display:inline-block;margin:.5rem .9rem .5rem 0}.button-link+.small-link{margin-left:.9rem}

/* Disclosure */
details{margin:.6rem 0}details>summary{cursor:pointer;font-weight:500;color:var(--ink)}
details>summary:hover{color:var(--accent)}
.danger-zone{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--line)}
.danger-zone>summary{color:var(--ink-2);font-size:.9rem;font-weight:400}
.danger-zone button{background:var(--surface);border-color:var(--bad-line);color:var(--bad)}.danger-zone button:hover{background:var(--bad-bg);border-color:var(--bad)}

/* Queue */
.filter-nav{display:flex;gap:.25rem;margin:0 0 1rem;overflow-x:auto;border-bottom:1px solid var(--line);scrollbar-width:none}
.filter-nav::-webkit-scrollbar{display:none}
.filter-nav a{display:flex;align-items:center;gap:.4rem;flex:none;margin-bottom:-1px;padding:.5rem .7rem;border-bottom:2px solid transparent;color:var(--ink-2);text-decoration:none}
.filter-nav a:hover{color:var(--ink)}
.filter-nav a.active{border-color:var(--accent);color:var(--ink);font-weight:550}
.count{min-width:1.35rem;padding:0 .35rem;border-radius:.35rem;background:color-mix(in srgb,var(--ink) 7%,transparent);color:var(--ink-2);font-size:.8rem;font-weight:500;text-align:center;font-variant-numeric:tabular-nums}
.count-alert{background:var(--bad-bg);color:var(--bad)}
.request-list{display:grid}
.card>.request-list{margin:0 -1.3rem -1.2rem;border-top:1px solid var(--line)}
.request-item{display:flex;align-items:flex-start;justify-content:space-between;gap:.5rem 1.5rem;padding:.85rem 1.3rem;border-bottom:1px solid var(--line);color:inherit;text-decoration:none}
.request-item:last-child{border-bottom:0;border-radius:0 0 .7rem .7rem}
.request-item:hover{background:var(--surface-2)}
.request-item strong{display:block;font-weight:550}
.request-item small{display:block}
.ri-main{min-width:0}
.ri-side{flex:none;max-width:48%;text-align:right}
.ri-side .pill{margin:0 0 .25rem .3rem}
.overdue{color:var(--bad);font-weight:500}
.empty{padding:1rem 0;color:var(--ink-2)}

/* Case */
.case-frame{display:grid;grid-template-columns:186px minmax(0,1fr);gap:1.75rem;align-items:start}
.case-frame.family{grid-template-columns:minmax(0,1fr);gap:0;max-width:760px}
.case-nav{position:sticky;top:1rem;display:grid;gap:1px}
.case-nav-group{margin:.85rem .55rem .2rem;font-size:.78rem;font-weight:500;color:var(--ink-2)}
.case-nav-group:first-child{margin-top:0}
.case-nav a{display:flex;align-items:center;justify-content:space-between;gap:.4rem;min-height:2.15rem;padding:.3rem .55rem;border-radius:.4rem;color:var(--ink-2);text-decoration:none}
.case-nav a:hover{background:color-mix(in srgb,var(--ink) 6%,transparent);color:var(--ink)}
.case-nav a.active{background:var(--surface);box-shadow:0 0 0 1px var(--line);color:var(--ink);font-weight:550}
.mark-done{display:inline-flex;color:var(--ok)}
.mark-attention{width:.5rem;height:.5rem;border-radius:50%;background:var(--warn);flex:none}
.case-nav-mobile{display:none}
.case-main{min-width:0}
.message{margin:0 0 .75rem;padding:.75rem .9rem;background:var(--surface-2);border-radius:.6rem}
.message blockquote{margin:0;padding:0;background:none;border:0;white-space:pre-wrap}
.message small{display:block;margin-top:.35rem}
.message.approved{background:var(--ok-bg)}
blockquote{margin:.6rem 0;padding:.6rem .85rem;background:var(--surface-2);border-radius:.45rem;white-space:pre-wrap;overflow-wrap:anywhere}
.meta-line{font-size:.88rem;color:var(--ink-2)}
.activity-item{padding:.8rem 0;border-bottom:1px solid var(--line)}.activity-item:last-child{border-bottom:0;padding-bottom:0}
.activity-item:first-of-type{padding-top:0}.activity-item p{margin:.3rem 0}.activity-item h3{margin:.15rem 0}
.table-wrap{overflow:auto}
table{width:100%;border-collapse:collapse}th,td{padding:.6rem .7rem .6rem 0;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:0}th{font-size:.82rem;font-weight:500;color:var(--ink-2)}

/* Examples */
.example-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem}
.example{display:flex;flex-direction:column;margin:0}
.example blockquote{margin:0 0 .75rem;padding:0;background:none;font-size:1.03rem}
.example-foot{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem;margin-top:auto}
.example-foot .pill,.example-foot .button-link{margin:0}.example-foot .button-link{min-height:2.2rem;padding:.25rem .7rem;font-size:.9rem}

/* Sign in */
.auth-page{display:flex;flex-direction:column;justify-content:center;width:100%;max-width:25rem;min-height:100vh;margin:0 auto;padding:1.5rem 1rem}
.auth-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem}.auth-head .brand{padding:0}
.auth-foot{margin:1rem 0 0;font-size:.84rem;color:var(--ink-2)}
.auth-page .card{margin:0;padding:1.4rem}
.auth-switch{display:grid;grid-template-columns:1fr 1fr;gap:2px;margin:0 0 .4rem;padding:2px;background:var(--surface-2);border-radius:.5rem}
.auth-switch a{padding:.35rem .4rem;border-radius:.4rem;color:var(--ink-2);font-size:.88rem;text-align:center;text-decoration:none}
.auth-switch a.active{background:var(--surface);box-shadow:0 0 0 1px var(--line);color:var(--ink);font-weight:550}
.auth-page button{width:100%}

/* Earlier cases screens */
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem;margin:1rem 0}
.stat{padding:.8rem 1rem;background:var(--surface);border:1px solid var(--line);border-radius:.6rem;color:var(--ink-2);font-size:.88rem}.stat strong{display:block;color:var(--ink);font-size:1.4rem;font-weight:600}
.filters{display:flex;flex-wrap:wrap;align-items:end;gap:.75rem;margin:0 0 1rem}.filters label{flex:1;min-width:180px;margin:0}.filters button{margin:0}
.next{background:var(--accent-soft);border-color:var(--accent-line)}
section[id]{scroll-margin-top:1rem}

@media(max-width:1180px){.case-main .two-col,.case-main .split{grid-template-columns:minmax(0,1fr);gap:0}.app-main{padding-left:1.5rem;padding-right:1.5rem}}
@media(max-width:860px){
html{font-size:15.5px}html.role-family{font-size:17px}
.app-shell{display:block}.sidebar{display:none}
.app-main{padding:.5rem 1rem calc(5.5rem + env(safe-area-inset-bottom))}
.topbar{margin-bottom:1rem}.topbar .brand{display:flex}.topbar-title{display:none}
.topbar-note{display:block;margin:-.6rem 0 1rem;font-size:.82rem;color:var(--ink-2)}
.tabbar{position:fixed;left:0;right:0;bottom:0;z-index:40;display:grid;grid-auto-flow:column;grid-auto-columns:1fr;padding:.25rem .25rem calc(.25rem + env(safe-area-inset-bottom));background:var(--surface);border-top:1px solid var(--line)}
.tabbar>a,.tabbar>details>summary{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.1rem;min-height:3.1rem;padding:.2rem;border-radius:.45rem;color:var(--ink-2);font-size:.74rem;font-weight:500;text-decoration:none;list-style:none;cursor:pointer}
.tabbar>details>summary::-webkit-details-marker{display:none}
.tabbar>a[aria-current],.tabbar>details[data-current]>summary{color:var(--accent)}
.tabbar .icon{width:1.4rem;height:1.4rem}
.tabbar>details{margin:0}
.more-menu{position:absolute;right:.5rem;bottom:calc(100% + .4rem);width:min(290px,calc(100vw - 1rem));padding:.4rem;background:var(--surface);border:1px solid var(--line);border-radius:.7rem;box-shadow:var(--shadow)}
.more-menu a{display:flex;align-items:center;gap:.6rem;min-height:2.75rem;padding:.3rem .6rem;border-radius:.4rem;color:var(--ink);text-decoration:none}
.more-menu a[aria-current]{background:var(--surface-2);font-weight:550}
.more-person{padding:.5rem .6rem .6rem;border-bottom:1px solid var(--line);margin-bottom:.3rem;font-size:.9rem}.more-person strong{display:block;font-weight:550}
.more-menu button{width:100%;margin:.3rem 0 0}
.case-frame{grid-template-columns:minmax(0,1fr);gap:.9rem}.case-frame.family{gap:0}
.case-frame>.case-nav{display:none}.case-frame.family>.case-nav{display:grid}
.case-nav-mobile{display:block;margin:0;background:var(--surface);border:1px solid var(--line);border-radius:.55rem}
.case-nav-mobile>summary{display:flex;align-items:center;justify-content:space-between;min-height:2.75rem;padding:.4rem .8rem;list-style:none}
.case-nav-mobile>summary::-webkit-details-marker{display:none}
.case-nav-mobile>summary::after{content:"";width:.5rem;height:.5rem;margin:-.2rem .2rem 0 0;border-right:2px solid var(--ink-2);border-bottom:2px solid var(--ink-2);transform:rotate(45deg)}
.case-nav-mobile[open]>summary::after{margin-top:.2rem;transform:rotate(225deg)}
.case-nav-mobile .case-nav{position:static;padding:0 .4rem .5rem}.case-nav-mobile .case-nav a{min-height:2.75rem}
.two-col,.grid,.split{grid-template-columns:minmax(0,1fr);gap:0}
.case-meta{gap:.5rem 1.5rem}
.stats{grid-template-columns:repeat(2,minmax(0,1fr))}
input:not([type=checkbox]),textarea,select{font-size:max(1rem,16px)}
}
@media(max-width:560px){
.card{padding:1rem}.card>.request-list{margin:0 -1rem -1rem}.request-item{flex-direction:column;padding:.8rem 1rem}
.ri-side{max-width:none;text-align:left}.ri-side .pill{margin:0 .3rem .25rem 0}
.page-title h1,.case-title h1{font-size:1.45rem}
.page-title .button-link{width:100%}
.card form>button,.button-row>*{width:100%}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
'''
