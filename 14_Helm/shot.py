import html, subprocess, sys, os, re
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
def shot(out, title, logs, maxlines=None):
    lines=[]
    for l in logs: lines += open(l).read().rstrip('\n').split('\n')
    if maxlines: lines=lines[:maxlines]
    body=''.join(('<span class=c>%s</span>\n'%html.escape(x)) if x.startswith('$ ') else html.escape(x)+'\n' for x in lines)
    w=min(1400, max(700, int(max(len(x) for x in lines)*8.45)+50)); h=len(lines)*19+80
    page=f"""<html><body style="margin:0;background:#1e1e1e"><div style="background:#1e1e1e;font:14px Menlo,monospace;color:#ddd">
<div style="background:#2d2d2d;padding:8px 12px;color:#aaa;text-align:center;position:relative">
<span style="position:absolute;left:12px;top:6px;color:#ff5f56">●</span><span style="position:absolute;left:30px;top:6px;color:#ffbd2e">●</span><span style="position:absolute;left:48px;top:6px;color:#27c93f">●</span>{html.escape(title)}</div>
<pre style="margin:0;padding:12px 18px;line-height:19px;white-space:pre">{body}</pre></div>
<style>.c{{color:#7ee787}}</style></body></html>"""
    p='/tmp/_shot.html' if False else os.environ['SP']+'/_shot.html'
    open(p,'w').write(page)
    subprocess.run([CHROME,'--headless','--disable-gpu','--hide-scrollbars',f'--window-size={w},{h}',f'--screenshot={os.path.abspath(out)}','file://'+p],capture_output=True)
    print(out, w, h)
L='logs/'
S='screenshots/'
jobs=[
 ('h14-cmd-01-create-lint.png','helm create + lint + template',['t1-01-create','t1-02-lint']),
 ('h14-cmd-02-install.png','helm install',['t1-03-install']),
 ('h14-cmd-03-list-status.png','helm list + status',['t1-04-list','t1-05-status']),
 ('h14-cmd-04-get.png','helm get',['t1-06-get'],60),
 ('h14-cmd-05-upgrade-history-rollback.png','helm upgrade + history + rollback',['t1-07-upgrade','t1-08-history','t1-09-rollback']),
 ('h14-cmd-06-repo-search.png','helm repo + search',['t1-10-repo','t1-11-search'],32),
 ('h14-cmd-07-uninstall.png','helm uninstall',['t1-12-uninstall']),
 ('h14-rb-01-install-upgrade.png','rollback lab: install -> upgrade -> verify',['t2-01-install','t2-02-upgrade1','t2-03-verify1']),
 ('h14-rb-02-upgrade-again.png','rollback lab: upgrade again -> verify',['t2-04-upgrade2','t2-05-verify2']),
 ('h14-rb-03-rollback-verify.png','rollback lab: rollback -> verify',['t2-06-rollback','t2-07-verify3']),
 ('h14-mini-01-lint-template.png','notes-chart: lint + template',['t3-01-lint','t3-02-template']),
 ('h14-mini-02-install.png','notes-chart: install (dev)',['t3-03-install']),
 ('h14-mini-03-upgrade-prod.png','notes-chart: upgrade to prod values',['t3-04-upgrade','t3-05-history']),
 ('h14-mini-04-bad-upgrade-rollback.png','notes-chart: bad upgrade -> rollback',['t3-06-bad','t3-07-rollback']),
 ('h14-mini-05-uninstall.png','notes-chart: uninstall',['t3-08-uninstall']),
]
for j in jobs: shot(S+j[0], 'parth@mac: '+j[1], [L+x+'.log' for x in j[2]], j[3] if len(j)>3 else None)
