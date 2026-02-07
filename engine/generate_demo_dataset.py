"""Generate synthetic screenshot demo dataset for Merlian.

Creates ~110 screenshots across 8 categories using Playwright + HTML templates.
All content is synthetic — fake names, fake amounts, fictional error codes.

Usage:
    cd engine && source .venv/bin/activate
    python generate_demo_dataset.py
"""

import asyncio
import random
import string
from pathlib import Path
from jinja2 import Template
from playwright.async_api import async_playwright

OUTPUT_DIR = Path(__file__).parent.parent / "demo-dataset"

# --- HTML Templates ---

ERROR_PAGE = Template("""<!DOCTYPE html><html><head><style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 60px; background: #f8f8f8; }
.error-box { max-width: 700px; margin: 40px auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.code { font-size: 72px; font-weight: 700; color: #dc2626; margin-bottom: 8px; }
.title { font-size: 24px; font-weight: 600; color: #111; margin-bottom: 16px; }
.msg { color: #666; line-height: 1.6; }
.url { font-family: monospace; font-size: 13px; color: #999; margin-top: 20px; }
</style></head><body>
<div class="error-box">
<div class="code">{{ code }}</div>
<div class="title">{{ title }}</div>
<div class="msg">{{ message }}</div>
<div class="url">{{ url }}</div>
</div></body></html>""")

TERMINAL_PAGE = Template("""<!DOCTYPE html><html><head><style>
body { margin: 0; padding: 0; background: #1e1e1e; }
.term { font-family: 'Menlo', 'Monaco', monospace; font-size: 13px; color: #d4d4d4; padding: 20px 24px; line-height: 1.5; white-space: pre-wrap; }
.prompt { color: #4ec9b0; }
.error { color: #f44747; }
.warning { color: #cca700; }
.info { color: #569cd6; }
.success { color: #6a9955; }
.dim { color: #666; }
</style></head><body>
<div class="term">{{ content }}</div>
</body></html>""")

RECEIPT_PAGE = Template("""<!DOCTYPE html><html><head><style>
body { font-family: -apple-system, sans-serif; margin: 0; padding: 40px; background: #fff; }
.receipt { max-width: 500px; margin: 0 auto; padding: 32px; border: 1px solid #e5e5e5; border-radius: 8px; }
.header { text-align: center; margin-bottom: 24px; }
.store { font-size: 20px; font-weight: 700; }
.date { color: #888; font-size: 13px; margin-top: 4px; }
.items { border-top: 1px solid #eee; padding-top: 16px; }
.item { display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; }
.total-line { display: flex; justify-content: space-between; padding: 12px 0; font-size: 16px; font-weight: 700; border-top: 2px solid #111; margin-top: 12px; }
.order-id { text-align: center; color: #999; font-size: 12px; margin-top: 20px; }
</style></head><body>
<div class="receipt">
<div class="header"><div class="store">{{ store }}</div><div class="date">{{ date }}</div></div>
<div class="items">
{% for item in items %}<div class="item"><span>{{ item.name }}</span><span>${{ "%.2f"|format(item.price) }}</span></div>{% endfor %}
</div>
<div class="total-line"><span>Total</span><span>${{ "%.2f"|format(total) }}</span></div>
<div class="order-id">Order #{{ order_id }}</div>
</div></body></html>""")

DASHBOARD_PAGE = Template("""<!DOCTYPE html><html><head><style>
body { font-family: -apple-system, sans-serif; margin: 0; padding: 24px; background: #f5f5f5; }
.dash { max-width: 900px; margin: 0 auto; }
.title { font-size: 22px; font-weight: 600; margin-bottom: 20px; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.card-label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
.card-value { font-size: 28px; font-weight: 700; margin-top: 4px; }
.card-delta { font-size: 13px; margin-top: 4px; }
.up { color: #16a34a; }
.down { color: #dc2626; }
.chart-placeholder { background: white; border-radius: 10px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); height: 200px; display: flex; align-items: flex-end; gap: 8px; padding-bottom: 12px; }
.bar { background: #3b82f6; border-radius: 4px 4px 0 0; flex: 1; }
</style></head><body>
<div class="dash">
<div class="title">{{ title }}</div>
<div class="cards">
{% for card in cards %}
<div class="card">
<div class="card-label">{{ card.label }}</div>
<div class="card-value">{{ card.value }}</div>
<div class="card-delta {{ 'up' if card.up else 'down' }}">{{ card.delta }}</div>
</div>
{% endfor %}
</div>
<div class="chart-placeholder">
{% for h in bar_heights %}<div class="bar" style="height: {{ h }}%"></div>{% endfor %}
</div>
</div></body></html>""")

MESSAGING_PAGE = Template("""<!DOCTYPE html><html><head><style>
body { font-family: -apple-system, sans-serif; margin: 0; padding: 0; background: #f8f8f8; }
.app { max-width: 800px; margin: 0 auto; display: flex; height: 600px; }
.sidebar { width: 240px; background: #2c1338; padding: 12px; }
.sidebar .ch { padding: 8px 12px; color: #ccc; font-size: 14px; border-radius: 6px; margin-bottom: 2px; cursor: pointer; }
.sidebar .ch.active { background: #4a154b; color: white; }
.sidebar .ch::before { content: "# "; color: #888; }
.main { flex: 1; background: white; display: flex; flex-direction: column; }
.header { padding: 12px 20px; border-bottom: 1px solid #eee; font-weight: 600; }
.messages { flex: 1; padding: 16px 20px; overflow-y: auto; }
.msg { margin-bottom: 16px; }
.msg-user { font-weight: 600; font-size: 14px; }
.msg-time { color: #999; font-size: 11px; margin-left: 8px; }
.msg-text { font-size: 14px; line-height: 1.5; margin-top: 2px; color: #333; }
.input-bar { padding: 12px 20px; border-top: 1px solid #eee; }
.input-bar input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
</style></head><body>
<div class="app">
<div class="sidebar">
{% for ch in channels %}<div class="ch {{ 'active' if loop.index == active_ch else '' }}">{{ ch }}</div>{% endfor %}
</div>
<div class="main">
<div class="header"># {{ channels[active_ch - 1] }}</div>
<div class="messages">
{% for m in messages %}<div class="msg"><span class="msg-user">{{ m.user }}</span><span class="msg-time">{{ m.time }}</span><div class="msg-text">{{ m.text }}</div></div>{% endfor %}
</div>
<div class="input-bar"><input type="text" placeholder="Message #{{ channels[active_ch - 1] }}"></div>
</div>
</div></body></html>""")

SETTINGS_PAGE = Template("""<!DOCTYPE html><html><head><style>
body { font-family: -apple-system, sans-serif; margin: 0; padding: 40px; background: #f5f5f5; }
.settings { max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 32px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.title { font-size: 22px; font-weight: 600; margin-bottom: 24px; }
.section { margin-bottom: 24px; }
.section-title { font-size: 13px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
.row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.row-label { font-size: 14px; }
.row-value { font-size: 14px; color: #666; }
.toggle { width: 40px; height: 22px; border-radius: 11px; position: relative; }
.toggle.on { background: #34c759; }
.toggle.off { background: #ccc; }
.toggle::after { content: ''; position: absolute; width: 18px; height: 18px; border-radius: 50%; background: white; top: 2px; }
.toggle.on::after { right: 2px; }
.toggle.off::after { left: 2px; }
</style></head><body>
<div class="settings">
<div class="title">{{ title }}</div>
{% for section in sections %}
<div class="section">
<div class="section-title">{{ section.title }}</div>
{% for row in section.rows %}
<div class="row">
<span class="row-label">{{ row.label }}</span>
{% if row.type == 'toggle' %}<div class="toggle {{ 'on' if row.value else 'off' }}"></div>
{% else %}<span class="row-value">{{ row.value }}</span>{% endif %}
</div>
{% endfor %}
</div>
{% endfor %}
</div></body></html>""")

CONFIRMATION_PAGE = Template("""<!DOCTYPE html><html><head><style>
body { font-family: -apple-system, sans-serif; margin: 0; padding: 60px; background: #f0fdf4; }
.box { max-width: 500px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.icon { font-size: 48px; margin-bottom: 16px; }
.title { font-size: 22px; font-weight: 600; margin-bottom: 8px; }
.subtitle { color: #666; font-size: 15px; margin-bottom: 24px; }
.code-box { background: #f5f5f5; border-radius: 8px; padding: 16px; font-family: monospace; font-size: 28px; letter-spacing: 4px; font-weight: 700; margin-bottom: 24px; }
.detail { font-size: 13px; color: #999; }
</style></head><body>
<div class="box">
<div class="icon">{{ icon }}</div>
<div class="title">{{ title }}</div>
<div class="subtitle">{{ subtitle }}</div>
{% if code %}<div class="code-box">{{ code }}</div>{% endif %}
<div class="detail">{{ detail }}</div>
</div></body></html>""")

CODE_PAGE = Template("""<!DOCTYPE html><html><head><style>
body { margin: 0; padding: 0; background: #1e1e1e; font-family: 'Menlo', monospace; font-size: 13px; }
.editor { display: flex; height: 600px; }
.sidebar { width: 200px; background: #252526; padding: 8px 0; }
.sidebar .file { padding: 4px 16px; color: #ccc; font-size: 12px; cursor: pointer; }
.sidebar .file.active { background: #37373d; color: white; }
.sidebar .folder { padding: 4px 16px; color: #888; font-size: 12px; }
.main { flex: 1; display: flex; flex-direction: column; }
.tabs { display: flex; background: #252526; }
.tab { padding: 8px 16px; font-size: 12px; color: #888; border-right: 1px solid #1e1e1e; }
.tab.active { background: #1e1e1e; color: #fff; }
.code { flex: 1; padding: 12px 16px; color: #d4d4d4; line-height: 1.6; white-space: pre; overflow: auto; }
.ln { display: inline-block; width: 40px; text-align: right; color: #555; margin-right: 16px; user-select: none; }
.kw { color: #569cd6; }
.str { color: #ce9178; }
.fn { color: #dcdcaa; }
.cm { color: #6a9955; }
.num { color: #b5cea8; }
</style></head><body>
<div class="editor">
<div class="sidebar">
<div class="folder">{{ project_name }}</div>
{% for f in files %}<div class="file {{ 'active' if f == active_file else '' }}">{{ f }}</div>{% endfor %}
</div>
<div class="main">
<div class="tabs">{% for f in tabs %}<div class="tab {{ 'active' if f == active_file else '' }}">{{ f }}</div>{% endfor %}</div>
<div class="code">{{ code_html }}</div>
</div>
</div></body></html>""")


# --- Data generators ---

def rand_id(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def rand_ip():
    return f"{random.randint(10,192)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

FAKE_NAMES = ["Alex Chen", "Jordan Kim", "Sam Rivera", "Morgan Lee", "Casey Park", "Riley Zhang", "Taylor Nguyen", "Quinn Davis"]
FAKE_STORES = ["CloudMart", "NovaBrew Coffee", "PixelGear Electronics", "FreshBasket Groceries", "TechHaven Store", "GreenLeaf Market"]
FAKE_DOMAINS = ["api.cloudnova.dev", "staging.pixelworks.io", "app.datastream.co", "service.nexthub.dev"]

def gen_errors():
    """Generate error page screenshots."""
    specs = [
        {"code": "403", "title": "Forbidden", "message": "You don't have permission to access this resource. Contact your administrator if you believe this is an error.", "url": f"https://{random.choice(FAKE_DOMAINS)}/api/v2/users"},
        {"code": "404", "title": "Page Not Found", "message": "The page you're looking for doesn't exist or has been moved.", "url": f"https://{random.choice(FAKE_DOMAINS)}/dashboard/settings"},
        {"code": "500", "title": "Internal Server Error", "message": "Something went wrong on our end. Our team has been notified and is working on a fix.", "url": f"https://{random.choice(FAKE_DOMAINS)}/api/checkout"},
        {"code": "502", "title": "Bad Gateway", "message": "The server received an invalid response from an upstream server.", "url": f"https://{random.choice(FAKE_DOMAINS)}/health"},
        {"code": "429", "title": "Too Many Requests", "message": "Rate limit exceeded. Please wait 60 seconds before trying again. Current limit: 100 requests/minute.", "url": f"https://{random.choice(FAKE_DOMAINS)}/api/search"},
        {"code": "401", "title": "Unauthorized", "message": "Your session has expired. Please sign in again to continue.", "url": f"https://{random.choice(FAKE_DOMAINS)}/api/me"},
        {"code": "503", "title": "Service Unavailable", "message": "We're currently undergoing scheduled maintenance. Expected completion: 15 minutes.", "url": f"https://{random.choice(FAKE_DOMAINS)}/status"},
        {"code": "408", "title": "Request Timeout", "message": "The server timed out waiting for the request. The operation took longer than 30 seconds.", "url": f"https://{random.choice(FAKE_DOMAINS)}/api/export"},
    ]
    return [(f"http-{s['code']}.png", ERROR_PAGE.render(**s)) for s in specs]

def gen_terminal():
    """Generate terminal/CLI screenshots."""
    specs = [
        {"name": "npm-install-fail.png", "content": f'<span class="prompt">~/project $</span> npm install\n<span class="info">added 847 packages in 12s</span>\n\n<span class="prompt">~/project $</span> npm run build\n\n<span class="error">ERROR in ./src/components/Dashboard.tsx\nModule not found: Error: Can\'t resolve \'./ChartWidget\'\n  at /Users/dev/project/src/components/Dashboard.tsx:4:1</span>\n\n<span class="error">ERROR in ./src/utils/api.ts\nTypeError: Cannot read properties of undefined (reading \'endpoint\')\n  at Object.&lt;anonymous&gt; (api.ts:22:15)</span>\n\n<span class="dim">webpack compiled with 2 errors</span>'},
        {"name": "python-traceback.png", "content": f'<span class="prompt">(.venv) ~/app $</span> python main.py\n\nTraceback (most recent call last):\n  File "main.py", line 45, in &lt;module&gt;\n    result = process_data(payload)\n  File "/app/core/processor.py", line 112, in process_data\n    validated = schema.validate(data)\n  File "/app/core/schema.py", line 67, in validate\n    raise ValidationError(f"Missing required field: \'{{field}}\'")\n<span class="error">core.schema.ValidationError: Missing required field: \'user_id\'</span>'},
        {"name": "git-merge-conflict.png", "content": f'<span class="prompt">~/repo $</span> git merge feature/auth\nAuto-merging src/auth/handler.ts\n<span class="error">CONFLICT (content): Merge conflict in src/auth/handler.ts</span>\nAuto-merging src/config.ts\n<span class="error">CONFLICT (content): Merge conflict in src/config.ts</span>\n<span class="warning">Automatic merge failed; fix conflicts and then commit the result.</span>\n\n<span class="prompt">~/repo $</span> git status\n<span class="error">both modified:   src/auth/handler.ts</span>\n<span class="error">both modified:   src/config.ts</span>'},
        {"name": "docker-build.png", "content": f'<span class="prompt">~/app $</span> docker build -t myapp:latest .\n\nStep 1/8 : FROM node:20-alpine\n<span class="info"> ---> a8b7c6d5e4f3</span>\nStep 2/8 : WORKDIR /app\nStep 3/8 : COPY package*.json ./\nStep 4/8 : RUN npm ci --production\n<span class="dim">npm warn deprecated inflight@1.0.6</span>\n<span class="dim">added 234 packages in 8.4s</span>\nStep 5/8 : COPY . .\nStep 6/8 : RUN npm run build\n<span class="success">Successfully compiled 42 modules</span>\nStep 7/8 : EXPOSE 3000\nStep 8/8 : CMD ["node", "dist/server.js"]\n<span class="success">Successfully built a1b2c3d4e5f6</span>\n<span class="success">Successfully tagged myapp:latest</span>'},
        {"name": "deploy-failed.png", "content": f'<span class="prompt">~/app $</span> vercel --prod\n\n<span class="info">Vercel CLI 33.5.1</span>\n<span class="info">Deploying ~/app to production</span>\n\nUploading [====================] 100%\nBuilding...\n\n<span class="error">Error: Build failed</span>\n<span class="error">Command "npm run build" exited with 1</span>\n\n<span class="error">ERROR  Type error: Property \'userId\' does not exist on type \'Session\'.</span>\n<span class="dim">  > 14 | const id = session.userId;</span>\n<span class="dim">       |                    ^</span>\n\n<span class="warning">Build failed. Check the logs above for details.</span>'},
        {"name": "pip-install.png", "content": f'<span class="prompt">(.venv) $</span> pip install torch torchvision\n\nCollecting torch\n  Downloading torch-2.5.1-cp312-cp312-macosx_14_0_arm64.whl (63.8 MB)\n     ━━━━━━━━━━━━━━━━━━━━ 63.8/63.8 MB 12.4 MB/s eta 0:00:00\nCollecting torchvision\n  Downloading torchvision-0.20.1-cp312-cp312-macosx_14_0_arm64.whl (1.8 MB)\n<span class="success">Successfully installed torch-2.5.1 torchvision-0.20.1 numpy-2.1.3 pillow-11.0.0</span>'},
        {"name": "test-output.png", "content": f'<span class="prompt">~/project $</span> pytest tests/ -v\n\ntests/test_auth.py::test_login <span class="success">PASSED</span>\ntests/test_auth.py::test_logout <span class="success">PASSED</span>\ntests/test_auth.py::test_refresh_token <span class="error">FAILED</span>\ntests/test_api.py::test_create_user <span class="success">PASSED</span>\ntests/test_api.py::test_delete_user <span class="success">PASSED</span>\ntests/test_api.py::test_update_user <span class="warning">SKIPPED</span>\ntests/test_search.py::test_basic_search <span class="success">PASSED</span>\ntests/test_search.py::test_fuzzy_search <span class="error">FAILED</span>\n\n<span class="error">FAILURES</span>\n<span class="error">test_refresh_token - AssertionError: Expected 200, got 401</span>\n<span class="error">test_fuzzy_search - IndexError: list index out of range</span>\n\n<span class="dim">6 passed, 2 failed, 1 skipped in 3.42s</span>'},
    ]
    return [(s["name"], TERMINAL_PAGE.render(content=s["content"])) for s in specs]

def gen_receipts():
    """Generate receipt/invoice screenshots."""
    results = []
    for i in range(10):
        store = random.choice(FAKE_STORES)
        items = []
        for _ in range(random.randint(3, 7)):
            item_names = ["Cappuccino", "Latte", "Cold Brew", "USB-C Cable", "Wireless Mouse", "Monitor Stand",
                         "Avocados (3)", "Sourdough Bread", "Oat Milk", "Chicken Breast", "Organic Eggs",
                         "Cloud Pro Plan", "API Credits", "Domain Renewal", "SSL Certificate"]
            items.append({"name": random.choice(item_names), "price": round(random.uniform(2.50, 89.99), 2)})
        total = sum(it["price"] for it in items)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        date = f"Jan {day}, 2026" if month == 1 else f"{'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[month-1]} {day}, 2026"
        html = RECEIPT_PAGE.render(store=store, date=date, items=items, total=total, order_id=rand_id(10))
        results.append((f"receipt-{i+1:02d}.png", html))
    return results

def gen_dashboards():
    """Generate dashboard/analytics screenshots."""
    specs = [
        {"title": "Analytics Dashboard — January 2026", "cards": [
            {"label": "Total Revenue", "value": "$48,291", "delta": "+12.3% vs last month", "up": True},
            {"label": "Active Users", "value": "8,412", "delta": "+5.7% vs last month", "up": True},
            {"label": "Churn Rate", "value": "2.1%", "delta": "-0.3% vs last month", "up": True},
        ]},
        {"title": "Deploy Metrics — Production", "cards": [
            {"label": "Deploys Today", "value": "14", "delta": "+3 vs yesterday", "up": True},
            {"label": "Avg Build Time", "value": "2m 34s", "delta": "+18s vs last week", "up": False},
            {"label": "Success Rate", "value": "92.8%", "delta": "-1.2% vs last week", "up": False},
        ]},
        {"title": "API Performance", "cards": [
            {"label": "Requests / min", "value": "12,847", "delta": "+22% peak hour", "up": True},
            {"label": "P95 Latency", "value": "142ms", "delta": "-8ms vs yesterday", "up": True},
            {"label": "Error Rate", "value": "0.12%", "delta": "+0.03% vs baseline", "up": False},
        ]},
        {"title": "Marketing — Campaign Overview", "cards": [
            {"label": "Impressions", "value": "245K", "delta": "+18% vs last week", "up": True},
            {"label": "Click Rate", "value": "3.2%", "delta": "+0.4% vs avg", "up": True},
            {"label": "Cost per Click", "value": "$0.42", "delta": "-$0.08 vs target", "up": True},
        ]},
        {"title": "Infrastructure — Cluster Health", "cards": [
            {"label": "CPU Usage", "value": "67%", "delta": "+12% vs yesterday", "up": False},
            {"label": "Memory", "value": "14.2 GB", "delta": "of 32 GB allocated", "up": True},
            {"label": "Disk I/O", "value": "340 MB/s", "delta": "within normal range", "up": True},
        ]},
    ]
    results = []
    for i, s in enumerate(specs):
        bars = [random.randint(20, 95) for _ in range(12)]
        html = DASHBOARD_PAGE.render(title=s["title"], cards=s["cards"], bar_heights=bars)
        results.append((f"dashboard-{i+1:02d}.png", html))
    return results

def gen_messaging():
    """Generate chat/messaging screenshots."""
    specs = [
        {"channels": ["general", "engineering", "design", "random", "standup"], "active_ch": 2, "messages": [
            {"user": "Alex Chen", "time": "10:32 AM", "text": "Just pushed the auth fix. Can someone review PR #247?"},
            {"user": "Jordan Kim", "time": "10:34 AM", "text": "On it. Is it just the token refresh logic?"},
            {"user": "Alex Chen", "time": "10:35 AM", "text": "Yeah, plus a migration for the sessions table. Should be backwards compatible."},
            {"user": "Sam Rivera", "time": "10:41 AM", "text": "FYI the staging deploy is stuck. Looks like the DB migration is timing out."},
            {"user": "Morgan Lee", "time": "10:43 AM", "text": "I'll check the connection pool. We hit this last week too."},
        ]},
        {"channels": ["general", "product", "support", "releases", "watercooler"], "active_ch": 4, "messages": [
            {"user": "Riley Zhang", "time": "3:15 PM", "text": "v2.4.0 is live! Release notes: https://docs.example.com/releases/2.4"},
            {"user": "Taylor Nguyen", "time": "3:18 PM", "text": "Nice! The new search filters are already getting positive feedback from beta users."},
            {"user": "Quinn Davis", "time": "3:22 PM", "text": "Any known issues we should watch for?"},
            {"user": "Riley Zhang", "time": "3:24 PM", "text": "One edge case with date filtering on Safari. Fix is in v2.4.1 which ships tomorrow."},
        ]},
        {"channels": ["team-alpha", "team-beta", "announcements", "help-desk", "social"], "active_ch": 1, "messages": [
            {"user": "Casey Park", "time": "9:05 AM", "text": "Standup: Yesterday I finished the payment integration tests. Today working on webhook retry logic."},
            {"user": "Morgan Lee", "time": "9:06 AM", "text": "Standup: Reviewed 3 PRs. Today: finishing the caching layer for the search API."},
            {"user": "Alex Chen", "time": "9:08 AM", "text": "Standup: Debugging the memory leak in the worker process. Found the issue — connection pool not releasing."},
            {"user": "Sam Rivera", "time": "9:10 AM", "text": "Standup: Design review for the new onboarding flow. Will share mockups in #design by EOD."},
        ]},
    ]
    results = []
    for i, s in enumerate(specs):
        html = MESSAGING_PAGE.render(**s)
        results.append((f"chat-{i+1:02d}.png", html))
    return results

def gen_settings():
    """Generate settings page screenshots."""
    specs = [
        {"title": "Account Settings", "sections": [
            {"title": "Profile", "rows": [
                {"label": "Display Name", "value": "Alex Chen", "type": "text"},
                {"label": "Email", "value": "alex@example.dev", "type": "text"},
                {"label": "Timezone", "value": "Pacific Time (UTC-8)", "type": "text"},
            ]},
            {"title": "Notifications", "rows": [
                {"label": "Email notifications", "value": True, "type": "toggle"},
                {"label": "Push notifications", "value": False, "type": "toggle"},
                {"label": "Weekly digest", "value": True, "type": "toggle"},
            ]},
            {"title": "Security", "rows": [
                {"label": "Two-factor authentication", "value": True, "type": "toggle"},
                {"label": "Session timeout", "value": "30 minutes", "type": "text"},
            ]},
        ]},
        {"title": "API Configuration", "sections": [
            {"title": "Endpoints", "rows": [
                {"label": "Base URL", "value": "https://api.cloudnova.dev/v2", "type": "text"},
                {"label": "Rate limit", "value": "1000 req/min", "type": "text"},
                {"label": "Timeout", "value": "30 seconds", "type": "text"},
            ]},
            {"title": "Features", "rows": [
                {"label": "Enable webhooks", "value": True, "type": "toggle"},
                {"label": "Debug mode", "value": False, "type": "toggle"},
                {"label": "Cache responses", "value": True, "type": "toggle"},
            ]},
        ]},
    ]
    results = []
    for i, s in enumerate(specs):
        html = SETTINGS_PAGE.render(**s)
        results.append((f"settings-{i+1:02d}.png", html))
    return results

def gen_confirmations():
    """Generate confirmation/2FA/booking screenshots."""
    specs = [
        {"icon": "&#x2705;", "title": "Email Verified", "subtitle": "Your email address has been confirmed.", "code": "", "detail": "You can now access all features of your account."},
        {"icon": "&#x1F512;", "title": "Verification Code", "subtitle": "Enter this code to complete sign-in.", "code": f"{random.randint(100000,999999)}", "detail": "This code expires in 10 minutes. Do not share it with anyone."},
        {"icon": "&#x2705;", "title": "Booking Confirmed", "subtitle": f"Your reservation at Hotel Lumière is confirmed.", "code": f"BK-{rand_id(8)}", "detail": "Check-in: Feb 15, 2026 • Check-out: Feb 18, 2026 • 1 room, 2 guests"},
        {"icon": "&#x1F4E6;", "title": "Order Confirmed", "subtitle": "Your order has been placed successfully.", "code": f"ORD-{rand_id(10)}", "detail": "Estimated delivery: Feb 12-14, 2026 • Total: $127.45"},
        {"icon": "&#x1F512;", "title": "Two-Factor Authentication", "subtitle": "Enter the code from your authenticator app.", "code": f"{random.randint(100000,999999)}", "detail": "If you've lost access to your authenticator, use a recovery code."},
        {"icon": "&#x2708;&#xFE0F;", "title": "Flight Booked", "subtitle": "SFO → NRT • Feb 20, 2026", "code": f"FLT-{rand_id(6)}", "detail": "Departure: 11:45 AM • Arrival: 4:30 PM+1 • Economy • 1 passenger"},
        {"icon": "&#x1F4B3;", "title": "Payment Successful", "subtitle": "Your payment of $49.99 has been processed.", "code": "", "detail": f"Transaction ID: TXN-{rand_id(12)} • Visa ending in {random.randint(1000,9999)}"},
    ]
    results = []
    for i, s in enumerate(specs):
        html = CONFIRMATION_PAGE.render(**s)
        results.append((f"confirm-{i+1:02d}.png", html))
    return results

def gen_code():
    """Generate code editor screenshots."""
    specs = [
        {"project_name": "merlian", "files": ["server.py", "merlian.py", "schema.py", "utils.py", "tests/"], "tabs": ["server.py", "merlian.py"], "active_file": "server.py",
         "code_html": '<span class="ln"> 1</span><span class="kw">from</span> fastapi <span class="kw">import</span> FastAPI, HTTPException\n<span class="ln"> 2</span><span class="kw">from</span> pydantic <span class="kw">import</span> BaseModel\n<span class="ln"> 3</span>\n<span class="ln"> 4</span><span class="cm"># Initialize the application</span>\n<span class="ln"> 5</span>app = FastAPI(title=<span class="str">"Merlian API"</span>)\n<span class="ln"> 6</span>\n<span class="ln"> 7</span><span class="kw">class</span> <span class="fn">SearchRequest</span>(BaseModel):\n<span class="ln"> 8</span>    query: str\n<span class="ln"> 9</span>    k: int = <span class="num">12</span>\n<span class="ln">10</span>    mode: str = <span class="str">"hybrid"</span>\n<span class="ln">11</span>\n<span class="ln">12</span>@app.post(<span class="str">"/search"</span>)\n<span class="ln">13</span><span class="kw">async def</span> <span class="fn">search</span>(req: SearchRequest):\n<span class="ln">14</span>    results = engine.<span class="fn">search</span>(req.query, k=req.k)\n<span class="ln">15</span>    <span class="kw">return</span> {<span class="str">"results"</span>: results}'},
        {"project_name": "web-app", "files": ["index.tsx", "App.tsx", "api.ts", "styles.css", "package.json"], "tabs": ["App.tsx", "api.ts"], "active_file": "App.tsx",
         "code_html": '<span class="ln"> 1</span><span class="kw">import</span> React, { useState, useEffect } <span class="kw">from</span> <span class="str">"react"</span>;\n<span class="ln"> 2</span><span class="kw">import</span> { fetchData } <span class="kw">from</span> <span class="str">"./api"</span>;\n<span class="ln"> 3</span>\n<span class="ln"> 4</span><span class="kw">export default function</span> <span class="fn">App</span>() {\n<span class="ln"> 5</span>  <span class="kw">const</span> [data, setData] = <span class="fn">useState</span>(<span class="kw">null</span>);\n<span class="ln"> 6</span>  <span class="kw">const</span> [loading, setLoading] = <span class="fn">useState</span>(<span class="kw">true</span>);\n<span class="ln"> 7</span>\n<span class="ln"> 8</span>  <span class="fn">useEffect</span>(() => {\n<span class="ln"> 9</span>    <span class="fn">fetchData</span>().<span class="fn">then</span>(d => {\n<span class="ln">10</span>      <span class="fn">setData</span>(d);\n<span class="ln">11</span>      <span class="fn">setLoading</span>(<span class="kw">false</span>);\n<span class="ln">12</span>    });\n<span class="ln">13</span>  }, []);\n<span class="ln">14</span>\n<span class="ln">15</span>  <span class="kw">if</span> (loading) <span class="kw">return</span> &lt;div&gt;Loading...&lt;/div&gt;;\n<span class="ln">16</span>  <span class="kw">return</span> &lt;div&gt;{data.title}&lt;/div&gt;;\n<span class="ln">17</span>}'},
    ]
    results = []
    for i, s in enumerate(specs):
        html = CODE_PAGE.render(**s)
        results.append((f"code-{i+1:02d}.png", html))
    return results


# --- Main generator ---

async def render_screenshots(items: list[tuple[str, str]], category: str, page):
    """Render HTML pages as screenshots."""
    cat_dir = OUTPUT_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    for filename, html in items:
        path = cat_dir / filename
        await page.set_content(html, wait_until="networkidle")
        await page.screenshot(path=str(path), full_page=False)
        print(f"  {category}/{filename}")


async def main():
    print("Generating Merlian demo dataset...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    categories = {
        "errors": gen_errors(),
        "code": gen_code(),
        "terminal": gen_terminal(),
        "receipts": gen_receipts(),
        "dashboards": gen_dashboards(),
        "messaging": gen_messaging(),
        "settings": gen_settings(),
        "confirmations": gen_confirmations(),
    }

    total = sum(len(v) for v in categories.values())
    print(f"Will generate {total} screenshots across {len(categories)} categories.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        for cat, items in categories.items():
            print(f"[{cat}] {len(items)} screenshots")
            await render_screenshots(items, cat, page)

        await browser.close()

    print(f"\nDone! {total} screenshots saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
