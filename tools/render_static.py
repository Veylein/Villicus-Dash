from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime
import os
import shutil

BASE = Path(__file__).parent.parent
REPO_ROOT = BASE.parent
TEMPLATES = BASE / 'templates'
STATIC = BASE / 'static'
OUT = REPO_ROOT / 'docs'

def render():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(['html', 'xml'])
    )
    # Provide `now()` and other safe globals to templates
    env.globals['now'] = lambda: datetime.utcnow()
    oauth_url = os.getenv('OAUTH_URL', '#')

    # Prepare demo contexts
    demo_guilds = [
        {"id": 111111, "name": "Alpha Community", "owner": True, "permissions": 8},
        {"id": 222222, "name": "Beta Squad", "owner": False, "permissions": 8},
        {"id": 333333, "name": "Gamma Guild", "owner": False, "permissions": 0},
    ]
    demo_settings = {
        'warns_to_punish': '3',
        'warn_punish_action': 'mute',
        'accent_color': '#6ee7b7',
        'theme': 'dark',
        'staff_roles_list': [
            {'id': 9991, 'level': 8, 'name': 'Moderators'},
            {'id': 9992, 'level': 5, 'name': 'Helpers'},
        ]
    }

    # Render index
    tmpl = env.get_template('index.html')
    html = tmpl.render(oauth_url=oauth_url)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    # write index
    with open(OUT / 'index.html', 'w', encoding='utf-8') as f:
        f.write(html)

    # render dashboard demo
    try:
        dtmpl = env.get_template('dashboard.html')
        dhtml = dtmpl.render(guilds=demo_guilds, admin_guilds=[g for g in demo_guilds if g.get('owner')])
        with open(OUT / 'dashboard.html', 'w', encoding='utf-8') as f:
            f.write(dhtml)
    except Exception:
        pass

    # render configure demo for a sample guild id
    try:
        ctxt = {'guild_id': 111111, 'settings': demo_settings}
        ctmpl = env.get_template('configure.html')
        chtml = ctmpl.render(**ctxt)
        with open(OUT / 'configure_111111.html', 'w', encoding='utf-8') as f:
            f.write(chtml)
    except Exception:
        pass

    # copy static assets
    if STATIC.exists():
        shutil.copytree(STATIC, OUT / 'static')

    print('Rendered static site to', OUT)

if __name__ == '__main__':
    render()
