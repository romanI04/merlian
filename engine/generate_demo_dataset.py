"""Generate realistic synthetic screenshot demo dataset for Merlian.

Creates screenshots that look like ACTUAL macOS screenshots people take —
with window chrome, browser frames, realistic app UIs.

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

# --- Shared CSS components ---

MACOS_CHROME = """
.macos-window { background: white; border-radius: 10px; box-shadow: 0 22px 70px 4px rgba(0,0,0,0.28), 0 0 0 1px rgba(0,0,0,0.08); overflow: hidden; }
.macos-titlebar { height: 38px; background: linear-gradient(180deg, #e8e6e8 0%, #d6d3d6 100%); display: flex; align-items: center; padding: 0 12px; position: relative; border-bottom: 1px solid #c0bdc0; }
.macos-titlebar.dark { background: linear-gradient(180deg, #3a3a3c 0%, #2c2c2e 100%); border-bottom: 1px solid #1c1c1e; }
.traffic-lights { display: flex; gap: 8px; }
.traffic-light { width: 12px; height: 12px; border-radius: 50%; }
.tl-close { background: #ff5f57; border: 1px solid #e0443e; }
.tl-min { background: #febc2e; border: 1px solid #dfa123; }
.tl-max { background: #28c840; border: 1px solid #1eab2f; }
.titlebar-text { position: absolute; left: 50%; transform: translateX(-50%); font-size: 13px; color: #4d4d4d; font-weight: 400; }
.macos-titlebar.dark .titlebar-text { color: #98989d; }
"""

BROWSER_CHROME = MACOS_CHROME + """
.browser-toolbar { height: 40px; background: #f2f2f7; border-bottom: 1px solid #d1d1d6; display: flex; align-items: center; padding: 0 12px; gap: 8px; }
.browser-toolbar.dark { background: #2c2c2e; border-bottom: 1px solid #3a3a3c; }
.nav-btns { display: flex; gap: 4px; }
.nav-btn { width: 28px; height: 28px; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #86868b; font-size: 16px; }
.url-bar { flex: 1; height: 28px; background: white; border-radius: 8px; border: 1px solid #d1d1d6; display: flex; align-items: center; padding: 0 10px; font-size: 12px; color: #86868b; }
.browser-toolbar.dark .url-bar { background: #1c1c1e; border-color: #3a3a3c; color: #98989d; }
.tab-bar { height: 36px; background: #e8e6e8; display: flex; align-items: flex-end; padding: 0 80px; gap: 0; }
.tab { height: 30px; background: #f2f2f7; border-radius: 8px 8px 0 0; padding: 0 16px; display: flex; align-items: center; font-size: 12px; color: #4d4d4d; border: 1px solid #d1d1d6; border-bottom: none; margin: 0 -1px; }
.tab.active { background: white; z-index: 1; }
"""

TERMINAL_CHROME = MACOS_CHROME + """
.terminal-body { background: #1e1e2e; font-family: 'Menlo', 'Monaco', 'SF Mono', monospace; font-size: 13px; color: #cdd6f4; padding: 16px; line-height: 1.6; white-space: pre-wrap; min-height: 500px; }
.prompt { color: #a6e3a1; }
.cmd { color: #cdd6f4; }
.error { color: #f38ba8; }
.warning { color: #f9e2af; }
.success { color: #a6e3a1; }
.info { color: #89b4fa; }
.dim { color: #585b70; }
.path { color: #89dceb; }
"""

VSCODE_CHROME = """
.vscode-window { background: #1e1e1e; border-radius: 10px; box-shadow: 0 22px 70px 4px rgba(0,0,0,0.28); overflow: hidden; }
.vscode-titlebar { height: 38px; background: #323233; display: flex; align-items: center; padding: 0 12px; }
.traffic-lights { display: flex; gap: 8px; }
.traffic-light { width: 12px; height: 12px; border-radius: 50%; }
.tl-close { background: #ff5f57; border: 1px solid #e0443e; }
.tl-min { background: #febc2e; border: 1px solid #dfa123; }
.tl-max { background: #28c840; border: 1px solid #1eab2f; }
.vscode-tabs { height: 35px; background: #252526; display: flex; border-bottom: 1px solid #1e1e1e; }
.vscode-tab { height: 35px; padding: 0 14px; display: flex; align-items: center; font-size: 13px; color: #969696; background: #2d2d2d; border-right: 1px solid #1e1e1e; }
.vscode-tab.active { background: #1e1e1e; color: #fff; border-top: 1px solid #007acc; }
.vscode-sidebar { width: 220px; background: #252526; border-right: 1px solid #1e1e1e; padding: 8px 0; }
.sidebar-section { padding: 4px 12px; font-size: 11px; color: #bbbbbb; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }
.sidebar-file { padding: 3px 12px 3px 28px; font-size: 13px; color: #cccccc; cursor: pointer; }
.sidebar-file:hover { background: #2a2d2e; }
.sidebar-file.active { background: #37373d; }
.vscode-body { display: flex; }
.vscode-editor { flex: 1; padding: 8px 0; }
.code-line { padding: 0 16px 0 60px; font-family: 'Menlo', monospace; font-size: 13px; line-height: 20px; color: #d4d4d4; position: relative; white-space: pre; }
.code-line .ln { position: absolute; left: 16px; width: 32px; text-align: right; color: #858585; }
.kw { color: #569cd6; }
.str { color: #ce9178; }
.fn { color: #dcdcaa; }
.cm { color: #6a9955; }
.num { color: #b5cea8; }
.type { color: #4ec9b0; }
.var { color: #9cdcfe; }
.op { color: #d4d4d4; }
.vscode-statusbar { height: 22px; background: #007acc; display: flex; align-items: center; padding: 0 10px; font-size: 12px; color: white; gap: 16px; }
.vscode-minimap { width: 60px; background: #1e1e1e; opacity: 0.5; }
"""

# --- Templates ---

ERROR_BROWSER = Template("""<!DOCTYPE html><html><head><style>
""" + BROWSER_CHROME + """
body { margin: 0; padding: 40px; background: #e5e5ea; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro', sans-serif; }
.page-content { padding: 80px 40px; text-align: center; }
.error-code { font-size: 120px; font-weight: 800; color: {{ color }}; letter-spacing: -4px; line-height: 1; }
.error-title { font-size: 28px; font-weight: 600; color: #1d1d1f; margin: 16px 0 12px; }
.error-msg { font-size: 16px; color: #86868b; max-width: 480px; margin: 0 auto; line-height: 1.5; }
.error-url { font-family: 'SF Mono', Menlo, monospace; font-size: 13px; color: #aeaeb2; margin-top: 24px; }
.error-btn { display: inline-block; margin-top: 24px; padding: 10px 24px; background: #007aff; color: white; border-radius: 8px; font-size: 15px; font-weight: 500; text-decoration: none; }
</style></head><body>
<div class="macos-window" style="max-width: 1100px; margin: 0 auto;">
  <div class="macos-titlebar"><div class="traffic-lights"><div class="traffic-light tl-close"></div><div class="traffic-light tl-min"></div><div class="traffic-light tl-max"></div></div><span class="titlebar-text">{{ tab_title }}</span></div>
  <div class="browser-toolbar"><div class="nav-btns"><span class="nav-btn">&larr;</span><span class="nav-btn">&rarr;</span></div><div class="url-bar"><span style="color:#1d1d1f;">{{ domain }}</span><span>{{ path }}</span></div></div>
  <div class="page-content">
    <div class="error-code">{{ code }}</div>
    <div class="error-title">{{ title }}</div>
    <div class="error-msg">{{ message }}</div>
    <div class="error-url">{{ url }}</div>
    <a class="error-btn" href="#">{{ button_text }}</a>
  </div>
</div></body></html>""")


TERMINAL = Template("""<!DOCTYPE html><html><head><style>
""" + TERMINAL_CHROME + """
body { margin: 0; padding: 40px; background: #0d0d11; font-family: -apple-system, sans-serif; }
</style></head><body>
<div class="macos-window" style="max-width: 1000px; margin: 0 auto;">
  <div class="macos-titlebar dark"><div class="traffic-lights"><div class="traffic-light tl-close"></div><div class="traffic-light tl-min"></div><div class="traffic-light tl-max"></div></div><span class="titlebar-text">{{ title }}</span></div>
  <div class="terminal-body">{{ content }}</div>
</div></body></html>""")


RECEIPT_EMAIL = Template("""<!DOCTYPE html><html><head><style>
""" + BROWSER_CHROME + """
body { margin: 0; padding: 40px; background: #e5e5ea; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.email-body { background: white; padding: 40px; }
.email-header { border-bottom: 1px solid #e5e7eb; padding-bottom: 24px; margin-bottom: 24px; }
.email-from { font-size: 13px; color: #6b7280; }
.email-subject { font-size: 22px; font-weight: 700; color: #111827; margin-top: 8px; }
.receipt-box { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; margin: 24px 0; }
.receipt-logo { font-size: 18px; font-weight: 700; margin-bottom: 16px; }
.receipt-item { display: flex; justify-content: space-between; padding: 8px 0; font-size: 14px; color: #374151; border-bottom: 1px solid #f3f4f6; }
.receipt-total { display: flex; justify-content: space-between; padding: 12px 0; font-size: 16px; font-weight: 700; color: #111827; border-top: 2px solid #111827; margin-top: 8px; }
.receipt-meta { font-size: 12px; color: #9ca3af; margin-top: 16px; }
.receipt-cta { display: inline-block; margin-top: 16px; padding: 10px 20px; background: #111827; color: white; border-radius: 8px; font-size: 14px; text-decoration: none; }
</style></head><body>
<div class="macos-window" style="max-width: 800px; margin: 0 auto;">
  <div class="macos-titlebar"><div class="traffic-lights"><div class="traffic-light tl-close"></div><div class="traffic-light tl-min"></div><div class="traffic-light tl-max"></div></div><span class="titlebar-text">Mail — {{ subject }}</span></div>
  <div class="email-body">
    <div class="email-header">
      <div class="email-from">From: {{ from_email }}<br>To: me<br>{{ date }}</div>
      <div class="email-subject">{{ subject }}</div>
    </div>
    <p style="color:#374151; font-size:15px;">Hi there,</p>
    <p style="color:#374151; font-size:15px;">{{ intro }}</p>
    <div class="receipt-box">
      <div class="receipt-logo">{{ store }}</div>
      {% for item in items %}
      <div class="receipt-item"><span>{{ item.name }}</span><span>${{ "%.2f"|format(item.price) }}</span></div>
      {% endfor %}
      <div class="receipt-total"><span>Total</span><span>${{ "%.2f"|format(total) }}</span></div>
      <div class="receipt-meta">Order #{{ order_id }} &middot; {{ payment_method }}</div>
    </div>
    <a class="receipt-cta" href="#">View Order Details</a>
  </div>
</div></body></html>""")


DASHBOARD_APP = Template("""<!DOCTYPE html><html><head><style>
""" + BROWSER_CHROME + """
body { margin: 0; padding: 40px; background: #e5e5ea; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.app-body { background: #f8fafc; min-height: 550px; }
.app-nav { background: white; border-bottom: 1px solid #e2e8f0; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; }
.app-nav-brand { font-size: 16px; font-weight: 700; color: #0f172a; }
.app-nav-links { display: flex; gap: 24px; font-size: 14px; color: #64748b; }
.app-nav-link.active { color: #0f172a; font-weight: 500; }
.app-content { padding: 24px; }
.page-title { font-size: 24px; font-weight: 700; color: #0f172a; margin-bottom: 20px; }
.metric-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.metric-card { background: white; border-radius: 12px; padding: 20px; border: 1px solid #e2e8f0; }
.metric-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; }
.metric-value { font-size: 30px; font-weight: 700; color: #0f172a; margin-top: 6px; }
.metric-delta { font-size: 13px; margin-top: 4px; font-weight: 500; }
.up { color: #16a34a; }
.down { color: #dc2626; }
.chart-box { background: white; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0; }
.chart-title { font-size: 16px; font-weight: 600; color: #0f172a; margin-bottom: 16px; }
.chart-placeholder { height: 200px; background: linear-gradient(180deg, rgba(59,130,246,0.08) 0%, rgba(59,130,246,0.02) 100%); border-radius: 8px; position: relative; overflow: hidden; }
.chart-line { position: absolute; bottom: 0; left: 0; right: 0; height: 100%; }
.chart-line svg { width: 100%; height: 100%; }
.chart-grid { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: space-between; padding: 8px 0; }
.chart-grid-line { border-bottom: 1px solid #f1f5f9; }
.table-box { background: white; border-radius: 12px; border: 1px solid #e2e8f0; margin-top: 24px; overflow: hidden; }
.table-header { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; padding: 12px 20px; font-size: 12px; color: #64748b; font-weight: 500; text-transform: uppercase; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
.table-row { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; padding: 14px 20px; font-size: 14px; color: #334155; border-bottom: 1px solid #f1f5f9; }
.status-badge { padding: 2px 10px; border-radius: 99px; font-size: 12px; font-weight: 500; display: inline-block; }
.status-active { background: #dcfce7; color: #166534; }
.status-pending { background: #fef3c7; color: #92400e; }
.status-failed { background: #fef2f2; color: #991b1b; }
</style></head><body>
<div class="macos-window" style="max-width: 1100px; margin: 0 auto;">
  <div class="macos-titlebar"><div class="traffic-lights"><div class="traffic-light tl-close"></div><div class="traffic-light tl-min"></div><div class="traffic-light tl-max"></div></div><span class="titlebar-text">{{ app_name }}</span></div>
  <div class="browser-toolbar"><div class="nav-btns"><span class="nav-btn">&larr;</span><span class="nav-btn">&rarr;</span></div><div class="url-bar">{{ url }}</div></div>
  <div class="app-body">
    <div class="app-nav"><span class="app-nav-brand">{{ app_name }}</span><div class="app-nav-links">{% for link in nav_links %}<span class="app-nav-link {{ 'active' if link == active_link else '' }}">{{ link }}</span>{% endfor %}</div></div>
    <div class="app-content">
      <div class="page-title">{{ page_title }}</div>
      <div class="metric-cards">{% for m in metrics %}<div class="metric-card"><div class="metric-label">{{ m.label }}</div><div class="metric-value">{{ m.value }}</div><div class="metric-delta {{ m.direction }}">{{ m.delta }}</div></div>{% endfor %}</div>
      <div class="chart-box">
        <div class="chart-title">{{ chart_title }}</div>
        <div class="chart-placeholder">
          <div class="chart-grid">{% for _ in range(5) %}<div class="chart-grid-line"></div>{% endfor %}</div>
          <div class="chart-line"><svg viewBox="0 0 800 200" preserveAspectRatio="none"><path d="{{ chart_path }}" fill="none" stroke="#3b82f6" stroke-width="2"/><path d="{{ chart_path }} L800,200 L0,200 Z" fill="rgba(59,130,246,0.08)"/></svg></div>
        </div>
      </div>
      {% if table_rows %}
      <div class="table-box">
        <div class="table-header">{% for h in table_headers %}<span>{{ h }}</span>{% endfor %}</div>
        {% for row in table_rows %}<div class="table-row">{% for cell in row %}<span>{% if 'status-' in cell %}<span class="status-badge {{ cell }}">{{ cell.replace('status-', '').title() }}</span>{% else %}{{ cell }}{% endif %}</span>{% endfor %}</div>{% endfor %}
      </div>
      {% endif %}
    </div>
  </div>
</div></body></html>""")


CHAT_APP = Template("""<!DOCTYPE html><html><head><style>
""" + MACOS_CHROME + """
body { margin: 0; padding: 40px; background: #e5e5ea; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.chat-body { display: flex; min-height: 550px; }
.chat-sidebar { width: 240px; background: #1a1d21; padding: 12px 0; }
.chat-ws { padding: 12px 16px; font-size: 15px; font-weight: 800; color: white; }
.chat-section { padding: 4px 16px; font-size: 12px; color: #9ea2a9; margin-top: 12px; }
.chat-channel { padding: 4px 16px; font-size: 14px; color: #d1d2d3; display: flex; align-items: center; gap: 6px; cursor: pointer; }
.chat-channel:hover { background: rgba(255,255,255,0.06); }
.chat-channel.active { background: #1164a3; border-radius: 6px; margin: 0 8px; padding: 4px 8px; }
.chat-main { flex: 1; background: white; display: flex; flex-direction: column; }
.chat-header { padding: 12px 20px; border-bottom: 1px solid #e5e5e5; font-size: 16px; font-weight: 700; color: #1d1c1d; }
.chat-messages { flex: 1; padding: 16px 20px; overflow-y: auto; }
.msg { display: flex; gap: 10px; margin-bottom: 16px; }
.msg-avatar { width: 36px; height: 36px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700; color: white; flex-shrink: 0; }
.msg-body { flex: 1; }
.msg-meta { font-size: 13px; margin-bottom: 2px; }
.msg-name { font-weight: 700; color: #1d1c1d; }
.msg-time { color: #9ea2a9; font-weight: 400; margin-left: 6px; }
.msg-text { font-size: 15px; color: #1d1c1d; line-height: 1.5; }
.msg-text code { background: #f0f0f0; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 13px; color: #e01e5a; }
.msg-text a { color: #1264a3; text-decoration: none; }
.chat-input { border-top: 1px solid #e5e5e5; padding: 12px 20px; }
.chat-input-box { border: 1px solid #d1d2d3; border-radius: 8px; padding: 10px 14px; font-size: 14px; color: #9ea2a9; }
</style></head><body>
<div class="macos-window" style="max-width: 1100px; margin: 0 auto;">
  <div class="macos-titlebar"><div class="traffic-lights"><div class="traffic-light tl-close"></div><div class="traffic-light tl-min"></div><div class="traffic-light tl-max"></div></div><span class="titlebar-text">{{ workspace }} — {{ channel }}</span></div>
  <div class="chat-body">
    <div class="chat-sidebar">
      <div class="chat-ws">{{ workspace }}</div>
      <div class="chat-section">Channels</div>
      {% for ch in channels %}<div class="chat-channel {{ 'active' if ch == channel else '' }}"># {{ ch }}</div>{% endfor %}
    </div>
    <div class="chat-main">
      <div class="chat-header"># {{ channel }}</div>
      <div class="chat-messages">
        {% for m in messages %}
        <div class="msg">
          <div class="msg-avatar" style="background:{{ m.color }}">{{ m.initial }}</div>
          <div class="msg-body">
            <div class="msg-meta"><span class="msg-name">{{ m.name }}</span><span class="msg-time">{{ m.time }}</span></div>
            <div class="msg-text">{{ m.text }}</div>
          </div>
        </div>
        {% endfor %}
      </div>
      <div class="chat-input"><div class="chat-input-box">Message #{{ channel }}</div></div>
    </div>
  </div>
</div></body></html>""")


CODE_EDITOR = Template("""<!DOCTYPE html><html><head><style>
""" + VSCODE_CHROME + """
body { margin: 0; padding: 40px; background: #0d0d11; font-family: -apple-system, sans-serif; }
</style></head><body>
<div class="vscode-window" style="max-width: 1100px; margin: 0 auto;">
  <div class="vscode-titlebar"><div class="traffic-lights"><div class="traffic-light tl-close"></div><div class="traffic-light tl-min"></div><div class="traffic-light tl-max"></div></div></div>
  <div class="vscode-tabs">{% for tab in tabs %}<div class="vscode-tab {{ 'active' if tab == active_tab else '' }}">{{ tab }}</div>{% endfor %}</div>
  <div class="vscode-body">
    <div class="vscode-sidebar">
      <div class="sidebar-section">Explorer</div>
      {% for f in files %}<div class="sidebar-file {{ 'active' if f == active_tab else '' }}">{{ f }}</div>{% endfor %}
    </div>
    <div class="vscode-editor">{{ code_lines }}</div>
    <div class="vscode-minimap"></div>
  </div>
  <div class="vscode-statusbar"><span>{{ branch }}</span><span>Ln {{ cursor_line }}, Col {{ cursor_col }}</span><span>{{ language }}</span><span>UTF-8</span></div>
</div></body></html>""")


CONFIRMATION_PAGE = Template("""<!DOCTYPE html><html><head><style>
""" + BROWSER_CHROME + """
body { margin: 0; padding: 40px; background: #e5e5ea; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.confirm-body { background: white; padding: 60px 40px; text-align: center; }
.confirm-icon { width: 64px; height: 64px; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; font-size: 32px; }
.icon-success { background: #dcfce7; color: #16a34a; }
.icon-info { background: #dbeafe; color: #2563eb; }
.icon-warning { background: #fef3c7; color: #d97706; }
.confirm-title { font-size: 24px; font-weight: 700; color: #111827; margin-bottom: 8px; }
.confirm-sub { font-size: 16px; color: #6b7280; max-width: 400px; margin: 0 auto; line-height: 1.5; }
.confirm-code { font-family: 'SF Mono', Menlo, monospace; font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #111827; margin: 24px 0; }
.confirm-detail { background: #f9fafb; border-radius: 12px; padding: 20px; margin: 24px auto; max-width: 400px; text-align: left; }
.confirm-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; }
.confirm-row-label { color: #6b7280; }
.confirm-row-value { color: #111827; font-weight: 500; }
.confirm-btn { display: inline-block; margin-top: 20px; padding: 12px 32px; background: #111827; color: white; border-radius: 10px; font-size: 15px; font-weight: 500; text-decoration: none; }
.confirm-timer { font-size: 13px; color: #9ca3af; margin-top: 12px; }
</style></head><body>
<div class="macos-window" style="max-width: 800px; margin: 0 auto;">
  <div class="macos-titlebar"><div class="traffic-lights"><div class="traffic-light tl-close"></div><div class="traffic-light tl-min"></div><div class="traffic-light tl-max"></div></div><span class="titlebar-text">{{ tab_title }}</span></div>
  <div class="browser-toolbar"><div class="nav-btns"><span class="nav-btn">&larr;</span><span class="nav-btn">&rarr;</span></div><div class="url-bar">{{ url }}</div></div>
  <div class="confirm-body">
    <div class="confirm-icon {{ icon_class }}">{{ icon }}</div>
    <div class="confirm-title">{{ title }}</div>
    <div class="confirm-sub">{{ subtitle }}</div>
    {% if code %}<div class="confirm-code">{{ code }}</div>{% endif %}
    {% if details %}
    <div class="confirm-detail">
      {% for d in details %}<div class="confirm-row"><span class="confirm-row-label">{{ d.label }}</span><span class="confirm-row-value">{{ d.value }}</span></div>{% endfor %}
    </div>
    {% endif %}
    {% if button_text %}<a class="confirm-btn" href="#">{{ button_text }}</a>{% endif %}
    {% if timer_text %}<div class="confirm-timer">{{ timer_text }}</div>{% endif %}
  </div>
</div></body></html>""")


SETTINGS_APP = Template("""<!DOCTYPE html><html><head><style>
""" + MACOS_CHROME + """
body { margin: 0; padding: 40px; background: #e5e5ea; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.settings-body { display: flex; min-height: 550px; }
.settings-sidebar { width: 220px; background: #f2f2f7; border-right: 1px solid #d1d1d6; padding: 8px; }
.settings-item { padding: 8px 12px; border-radius: 8px; font-size: 13px; color: #1d1d1f; display: flex; align-items: center; gap: 8px; cursor: pointer; }
.settings-item:hover { background: rgba(0,0,0,0.04); }
.settings-item.active { background: #007aff; color: white; }
.settings-item .icon { width: 28px; height: 28px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 16px; }
.settings-main { flex: 1; background: white; padding: 24px 32px; }
.settings-title { font-size: 28px; font-weight: 700; color: #1d1d1f; margin-bottom: 24px; }
.settings-group { margin-bottom: 24px; }
.settings-group-title { font-size: 13px; color: #86868b; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; }
.settings-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #f2f2f7; }
.settings-label { font-size: 15px; color: #1d1d1f; }
.settings-desc { font-size: 13px; color: #86868b; margin-top: 2px; }
.toggle { width: 42px; height: 26px; border-radius: 13px; position: relative; }
.toggle.on { background: #34c759; }
.toggle.off { background: #e5e5ea; }
.toggle-knob { width: 22px; height: 22px; border-radius: 11px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.2); position: absolute; top: 2px; }
.toggle.on .toggle-knob { right: 2px; }
.toggle.off .toggle-knob { left: 2px; }
.select-box { padding: 6px 12px; border: 1px solid #d1d1d6; border-radius: 6px; font-size: 14px; color: #1d1d1f; background: white; }
</style></head><body>
<div class="macos-window" style="max-width: 900px; margin: 0 auto;">
  <div class="macos-titlebar"><div class="traffic-lights"><div class="traffic-light tl-close"></div><div class="traffic-light tl-min"></div><div class="traffic-light tl-max"></div></div><span class="titlebar-text">{{ window_title }}</span></div>
  <div class="settings-body">
    <div class="settings-sidebar">
      {% for item in sidebar_items %}<div class="settings-item {{ 'active' if item.name == active_item else '' }}"><div class="icon" style="background:{{ item.color }}; color:white;">{{ item.icon }}</div>{{ item.name }}</div>{% endfor %}
    </div>
    <div class="settings-main">
      <div class="settings-title">{{ page_title }}</div>
      {% for group in groups %}
      <div class="settings-group">
        <div class="settings-group-title">{{ group.title }}</div>
        {% for row in group.rows %}
        <div class="settings-row">
          <div><div class="settings-label">{{ row.label }}</div>{% if row.desc %}<div class="settings-desc">{{ row.desc }}</div>{% endif %}</div>
          {% if row.type == 'toggle' %}<div class="toggle {{ 'on' if row.value else 'off' }}"><div class="toggle-knob"></div></div>{% elif row.type == 'select' %}<div class="select-box">{{ row.value }}</div>{% else %}<div style="font-size:14px; color:#86868b;">{{ row.value }}</div>{% endif %}
        </div>
        {% endfor %}
      </div>
      {% endfor %}
    </div>
  </div>
</div></body></html>""")


# --- Data generators ---

def rand_id(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def rand_chart_path():
    pts = []
    y = random.randint(80, 140)
    for x in range(0, 801, 40):
        y += random.randint(-30, 30)
        y = max(20, min(180, y))
        pts.append(f"{x},{y}")
    return "M" + " L".join(pts)

STORES = ["Whole Foods Market", "Blue Bottle Coffee", "Sweetgreen", "Apple Store",
          "Target", "Amazon Fresh", "Trader Joe's", "Shake Shack", "Chipotle"]
ITEMS = ["Organic Oat Milk", "Cold Brew Coffee", "Avocado Toast", "USB-C Hub",
         "AirPods Pro", "Standing Desk Mat", "Protein Bar Pack", "Monitor Light",
         "Mechanical Keyboard", "Noise Canceling Headphones", "iPad Case",
         "Lightning Cable", "Yoga Mat", "Water Bottle", "Backpack"]

PEOPLE = [
    {"name": "Sarah Chen", "color": "#e91e63", "initial": "S"},
    {"name": "Marcus Rivera", "color": "#9c27b0", "initial": "M"},
    {"name": "Priya Patel", "color": "#2196f3", "initial": "P"},
    {"name": "Jake Thompson", "color": "#ff9800", "initial": "J"},
    {"name": "Emma Liu", "color": "#4caf50", "initial": "E"},
    {"name": "Alex Kim", "color": "#00bcd4", "initial": "A"},
]


def gen_errors():
    errors = [
        {"code": "403", "title": "Forbidden", "color": "#dc2626", "message": "You don't have permission to access this resource. Please check your credentials or contact your administrator.",
         "domain": "app.vercel.com", "path": "/dashboard/deployments", "url": "https://app.vercel.com/dashboard/deployments", "tab_title": "403 Forbidden — Vercel", "button_text": "Go to Dashboard"},
        {"code": "404", "title": "Page Not Found", "color": "#6b7280", "message": "The page you're looking for doesn't exist or has been moved. Check the URL or navigate back to the homepage.",
         "domain": "docs.stripe.com", "path": "/api/v2/charges/legacy", "url": "https://docs.stripe.com/api/v2/charges/legacy", "tab_title": "404 — Stripe Docs", "button_text": "Go to API Reference"},
        {"code": "500", "title": "Internal Server Error", "color": "#dc2626", "message": "Something went wrong on our end. Our team has been notified and is investigating. Please try again in a few minutes.",
         "domain": "api.openai.com", "path": "/v1/chat/completions", "url": "https://api.openai.com/v1/chat/completions", "tab_title": "500 — OpenAI API", "button_text": "Check Status Page"},
        {"code": "502", "title": "Bad Gateway", "color": "#ea580c", "message": "The server received an invalid response from the upstream server. This is usually a temporary issue with our infrastructure.",
         "domain": "render.com", "path": "/dashboard/services/my-api", "url": "https://render.com/dashboard/services/my-api", "tab_title": "502 — Render", "button_text": "View Logs"},
        {"code": "429", "title": "Too Many Requests", "color": "#d97706", "message": "Rate limit exceeded. You've made too many requests in a short period. Please wait 60 seconds before trying again.",
         "domain": "api.anthropic.com", "path": "/v1/messages", "url": "https://api.anthropic.com/v1/messages", "tab_title": "429 Rate Limited — Anthropic", "button_text": "View Rate Limits"},
        {"code": "401", "title": "Unauthorized", "color": "#7c3aed", "message": "Your authentication token has expired. Please sign in again to continue accessing this resource.",
         "domain": "github.com", "path": "/settings/tokens", "url": "https://github.com/settings/tokens", "tab_title": "401 — GitHub", "button_text": "Sign In"},
        {"code": "503", "title": "Service Unavailable", "color": "#dc2626", "message": "This service is currently undergoing scheduled maintenance. Expected completion: 2:30 PM PST.",
         "domain": "status.aws.amazon.com", "path": "/", "url": "https://status.aws.amazon.com/", "tab_title": "503 — AWS Status", "button_text": "Subscribe to Updates"},
    ]
    return [(f"errors/http-{e['code']}.png", ERROR_BROWSER.render(**e)) for e in errors]


def gen_terminals():
    terms = [
        {"title": "Terminal — npm run build", "content": """<span class="path">~/project</span> <span class="prompt">$</span> <span class="cmd">npm install</span>
<span class="success">added 847 packages in 12s</span>

<span class="path">~/project</span> <span class="prompt">$</span> <span class="cmd">npm run build</span>

<span class="error">ERROR in ./src/components/Dashboard.tsx</span>
<span class="error">Module not found: Error: Can't resolve './ChartWidget'</span>
  at /Users/dev/project/src/components/Dashboard.tsx:4:1

<span class="error">ERROR in ./src/utils/api.ts</span>
<span class="error">TypeError: Cannot read properties of undefined (reading 'endpoint')</span>
  at Object.&lt;anonymous&gt; (api.ts:22:15)

<span class="error">webpack compiled with 2 errors</span>"""},

        {"title": "Terminal — python main.py", "content": """<span class="path">(.venv)</span> <span class="path">~/app</span> <span class="prompt">$</span> <span class="cmd">python main.py</span>
<span class="dim">INFO:     Loading configuration from config.yaml</span>
<span class="dim">INFO:     Connecting to database...</span>
<span class="dim">INFO:     Connected. Processing 1,247 records.</span>

<span class="error">Traceback (most recent call last):</span>
  File "main.py", line 45, in &lt;module&gt;
    result = process_data(payload)
  File "/app/core/processor.py", line 112, in process_data
    validated = schema.validate(data)
  File "/app/core/schema.py", line 67, in validate
    raise ValidationError(f"Missing required field: 'user_id'")
<span class="error">core.schema.ValidationError: Missing required field: 'user_id'</span>
<span class="error">  in record #847 of batch 'users_2024_q4.json'</span>"""},

        {"title": "Terminal — git merge", "content": """<span class="path">~/project</span> <span class="prompt">$</span> <span class="cmd">git merge feature/auth-refactor</span>
<span class="warning">Auto-merging src/auth/middleware.ts</span>
<span class="error">CONFLICT (content): Merge conflict in src/auth/middleware.ts</span>
<span class="warning">Auto-merging src/auth/session.ts</span>
<span class="error">CONFLICT (content): Merge conflict in src/auth/session.ts</span>
<span class="error">Automatic merge failed; fix conflicts and then commit the result.</span>

<span class="path">~/project</span> <span class="prompt">$</span> <span class="cmd">git status</span>
On branch main
You have unmerged paths.
  (fix conflicts and run "git commit")

Unmerged paths:
  <span class="error">both modified:   src/auth/middleware.ts</span>
  <span class="error">both modified:   src/auth/session.ts</span>"""},

        {"title": "Terminal — docker build", "content": """<span class="path">~/app</span> <span class="prompt">$</span> <span class="cmd">docker build -t myapp:latest .</span>
<span class="dim">[+] Building 34.2s (12/15)</span>
 => [internal] load build definition from Dockerfile                    0.0s
 => [internal] load .dockerignore                                       0.0s
 => [1/12] FROM node:20-alpine@sha256:a1b2c3d4                        2.1s
 => [2/12] WORKDIR /app                                                 0.0s
 => [3/12] COPY package*.json ./                                        0.0s
 => [4/12] RUN npm ci                                                  18.4s
 => [5/12] COPY . .                                                     0.3s
 => [6/12] RUN npm run build                                           12.7s
<span class="error"> => ERROR [6/12] RUN npm run build</span>
<span class="error">------</span>
<span class="error"> > [6/12] RUN npm run build:</span>
<span class="error">#10 11.23 Error: Cannot find module 'react-dom/client'</span>
<span class="error">#10 11.23 Require stack:</span>
<span class="error">#10 11.23 - /app/src/index.tsx</span>
<span class="error">------</span>
<span class="error">executor failed running [/bin/sh -c npm run build]: exit code: 1</span>"""},

        {"title": "Terminal — vercel deploy", "content": """<span class="path">~/app</span> <span class="prompt">$</span> <span class="cmd">vercel --prod</span>
<span class="info">Vercel CLI 33.5.1</span>
<span class="dim">Deploying ~/app to production</span>
<span class="dim">Uploading...</span>
<span class="success">Building...</span>

<span class="error">Error: Build failed</span>
<span class="error">Command "npm run build" exited with 1</span>

<span class="error">ERROR  Type error: Property 'userId' does not exist on type 'Session'</span>
<span class="error">  > 14 | const id = session.userId</span>
<span class="error">       |                    ^^^^^^^</span>

<span class="error">Build failed. Check the logs above for details.</span>
<span class="dim">Learn more: https://vercel.com/docs/concepts/deployments/build-step</span>"""},

        {"title": "Terminal — pytest", "content": """<span class="path">(.venv)</span> <span class="path">~/app</span> <span class="prompt">$</span> <span class="cmd">pytest tests/ -v</span>
<span class="dim">============================= test session starts ==============================</span>
<span class="dim">platform darwin -- Python 3.12.1, pytest-7.4.4</span>
<span class="dim">collected 24 items</span>

tests/test_auth.py::test_login <span class="success">PASSED</span>
tests/test_auth.py::test_logout <span class="success">PASSED</span>
tests/test_auth.py::test_refresh_token <span class="error">FAILED</span>
tests/test_api.py::test_create_user <span class="success">PASSED</span>
tests/test_api.py::test_delete_user <span class="success">PASSED</span>
tests/test_api.py::test_update_user <span class="warning">SKIPPED</span>
tests/test_search.py::test_basic_search <span class="success">PASSED</span>
tests/test_search.py::test_fuzzy_match <span class="error">FAILED</span>

<span class="error">================================== FAILURES ===================================</span>
<span class="error">____________________________ test_refresh_token ________________________________</span>
    def test_refresh_token():
        token = auth.refresh("expired_token_abc123")
<span class="error">>       assert token.is_valid()</span>
<span class="error">E       AssertionError: Token expired at 2024-12-15T08:30:00Z</span>

<span class="dim">======================== 2 failed, 5 passed, 1 skipped ========================</span>"""},
    ]
    return [(f"terminal/{['npm-build-fail', 'python-traceback', 'git-merge-conflict', 'docker-build-fail', 'vercel-deploy-fail', 'pytest-results'][i]}.png", TERMINAL.render(**t)) for i, t in enumerate(terms)]


def gen_receipts():
    results = []
    for i in range(8):
        store = random.choice(STORES)
        n_items = random.randint(3, 7)
        items = [{"name": random.choice(ITEMS), "price": round(random.uniform(3.99, 89.99), 2)} for _ in range(n_items)]
        total = sum(it["price"] for it in items)
        payment = random.choice(["Visa ending in 4242", "Apple Pay", "Mastercard ending in 8910", "Amex ending in 3001"])
        date = f"Jan {random.randint(1,28)}, 2026"
        subject = f"Your {store} receipt — ${total:.2f}"
        from_email = f"receipts@{store.lower().replace(' ', '').replace(chr(39), '')}.com"
        intro = f"Thanks for your purchase! Here's a summary of your order."
        results.append((f"receipts/receipt-{i+1:02d}.png", RECEIPT_EMAIL.render(
            store=store, items=items, total=total, order_id=rand_id(),
            subject=subject, from_email=from_email, date=date, intro=intro,
            payment_method=payment,
        )))
    return results


def gen_dashboards():
    dashboards = [
        {
            "app_name": "Vercel", "url": "app.vercel.com/analytics",
            "nav_links": ["Overview", "Deployments", "Analytics", "Domains", "Settings"], "active_link": "Analytics",
            "page_title": "Analytics", "chart_title": "Requests per hour",
            "metrics": [
                {"label": "Total Requests", "value": "2.4M", "delta": "+12.3% vs last week", "direction": "up"},
                {"label": "Avg Response", "value": "142ms", "delta": "-8ms vs last week", "direction": "up"},
                {"label": "Error Rate", "value": "0.12%", "delta": "+0.03%", "direction": "down"},
                {"label": "Bandwidth", "value": "8.2 GB", "delta": "+1.1 GB", "direction": "up"},
            ],
            "table_headers": ["Endpoint", "Requests", "P95 Latency", "Status"],
            "table_rows": [
                ["/api/users", "423K", "89ms", "status-active"],
                ["/api/search", "312K", "234ms", "status-pending"],
                ["/api/auth/login", "156K", "45ms", "status-active"],
                ["/api/webhooks", "89K", "567ms", "status-failed"],
                ["/api/billing", "34K", "123ms", "status-active"],
            ],
        },
        {
            "app_name": "Stripe Dashboard", "url": "dashboard.stripe.com/payments",
            "nav_links": ["Home", "Payments", "Customers", "Products", "Developers"], "active_link": "Payments",
            "page_title": "Payments", "chart_title": "Revenue (last 30 days)",
            "metrics": [
                {"label": "Gross Volume", "value": "$84,291", "delta": "+23.1% vs last month", "direction": "up"},
                {"label": "Successful", "value": "1,847", "delta": "+156 transactions", "direction": "up"},
                {"label": "Refunded", "value": "$1,205", "delta": "-$342 vs last month", "direction": "up"},
                {"label": "Net Volume", "value": "$83,086", "delta": "+24.7%", "direction": "up"},
            ],
            "table_headers": ["Description", "Amount", "Date", "Status"],
            "table_rows": [
                ["Pro Plan — Annual", "$299.00", "Feb 6, 2026", "status-active"],
                ["Enterprise Add-on", "$149.00", "Feb 5, 2026", "status-active"],
                ["Team Plan — Monthly", "$49.00", "Feb 5, 2026", "status-pending"],
                ["Starter Plan", "$19.00", "Feb 4, 2026", "status-failed"],
                ["API Credits Top-up", "$500.00", "Feb 3, 2026", "status-active"],
            ],
        },
        {
            "app_name": "PostHog", "url": "app.posthog.com/insights",
            "nav_links": ["Insights", "Dashboards", "People", "Experiments", "Data"], "active_link": "Insights",
            "page_title": "Product Analytics", "chart_title": "Daily Active Users",
            "metrics": [
                {"label": "DAU", "value": "12,847", "delta": "+18% vs last week", "direction": "up"},
                {"label": "Sessions", "value": "34.2K", "delta": "+2.1K", "direction": "up"},
                {"label": "Avg Duration", "value": "4m 23s", "delta": "+12s", "direction": "up"},
                {"label": "Retention", "value": "67.3%", "delta": "-2.1%", "direction": "down"},
            ],
            "table_headers": ["Event", "Count", "Unique Users", "Trend"],
            "table_rows": [
                ["pageview", "89,234", "12,847", "status-active"],
                ["search_performed", "23,456", "8,912", "status-active"],
                ["signup_completed", "1,234", "1,234", "status-active"],
                ["payment_initiated", "567", "423", "status-pending"],
            ],
        },
    ]
    results = []
    for i, d in enumerate(dashboards):
        d["chart_path"] = rand_chart_path()
        results.append((f"dashboards/dashboard-{i+1:02d}.png", DASHBOARD_APP.render(**d)))
    return results


def gen_chats():
    chats = [
        {
            "workspace": "Acme Corp", "channel": "engineering",
            "channels": ["general", "engineering", "design", "random", "incidents"],
            "messages": [
                {**PEOPLE[0], "time": "10:32 AM", "text": "Just pushed the auth fix. Can someone review <a href='#'>PR #247</a>?"},
                {**PEOPLE[3], "time": "10:34 AM", "text": "On it. Is it just the token refresh logic?"},
                {**PEOPLE[0], "time": "10:35 AM", "text": "Yeah, mainly <code>refreshToken()</code> in <code>auth/session.ts</code>. Also fixed the race condition we discussed yesterday."},
                {**PEOPLE[4], "time": "10:41 AM", "text": "Heads up — CI is failing on <code>main</code>. Looks like a flaky test in <code>test_search.py</code>. I'm looking into it."},
                {**PEOPLE[1], "time": "10:45 AM", "text": "Related: the search latency spike we saw last night was caused by a missing index on <code>users.email</code>. Deployed a fix at 3am. P95 back to normal."},
                {**PEOPLE[3], "time": "10:52 AM", "text": "PR approved. Nice catch on the race condition. Ship it!"},
            ],
        },
        {
            "workspace": "Acme Corp", "channel": "incidents",
            "channels": ["general", "engineering", "design", "random", "incidents"],
            "messages": [
                {**PEOPLE[1], "time": "2:15 PM", "text": "Incident: API returning 502 errors for ~15% of requests. Investigating."},
                {**PEOPLE[5], "time": "2:18 PM", "text": "Confirmed. Seeing elevated error rates in Datadog. Looks like it started around 2:10 PM."},
                {**PEOPLE[1], "time": "2:23 PM", "text": "Root cause: one of the database replicas fell behind. Connection pool is saturated. Removing the unhealthy replica from the pool now."},
                {**PEOPLE[4], "time": "2:25 PM", "text": "Customer reports coming in on Twitter and support channels. Should we post a status update?"},
                {**PEOPLE[1], "time": "2:28 PM", "text": "Fix deployed. Error rates dropping. <code>replica-3</code> removed, traffic rerouted to healthy nodes. Will monitor for 30 mins."},
                {**PEOPLE[5], "time": "2:45 PM", "text": "All clear. Error rate back to baseline. Posting postmortem summary to #engineering."},
            ],
        },
        {
            "workspace": "Acme Corp", "channel": "general",
            "channels": ["general", "engineering", "design", "random", "incidents"],
            "messages": [
                {**PEOPLE[2], "time": "9:05 AM", "text": "Good morning team! Standup notes:\n- Yesterday: Finished the payment integration tests\n- Today: Working on webhook retry logic\n- Blocker: Need access to the staging Stripe account"},
                {**PEOPLE[4], "time": "9:08 AM", "text": "I can get you staging access. DM me your email."},
                {**PEOPLE[3], "time": "9:12 AM", "text": "Standup:\n- Yesterday: Reviewed 3 PRs, fixed the flaky CI test\n- Today: Starting on the new onboarding flow\n- No blockers"},
                {**PEOPLE[0], "time": "9:15 AM", "text": "Reminder: design review at 2pm today. @Priya can you share the updated mockups in #design before then?"},
                {**PEOPLE[2], "time": "9:17 AM", "text": "Will do! Uploading the Figma link now."},
            ],
        },
    ]
    return [(f"messaging/chat-{i+1:02d}.png", CHAT_APP.render(**c)) for i, c in enumerate(chats)]


def gen_code():
    codes = [
        {
            "tabs": ["server.py", "models.py", "config.yaml"], "active_tab": "server.py",
            "files": ["server.py", "models.py", "routes/", "config.yaml", "tests/", "requirements.txt"],
            "branch": "main", "cursor_line": 24, "cursor_col": 15, "language": "Python",
            "code_lines": "\n".join([
                '<div class="code-line"><span class="ln">1</span><span class="kw">from</span> fastapi <span class="kw">import</span> FastAPI, HTTPException</div>',
                '<div class="code-line"><span class="ln">2</span><span class="kw">from</span> pydantic <span class="kw">import</span> BaseModel</div>',
                '<div class="code-line"><span class="ln">3</span><span class="kw">import</span> <span class="var">redis</span></div>',
                '<div class="code-line"><span class="ln">4</span></div>',
                '<div class="code-line"><span class="ln">5</span><span class="var">app</span> = <span class="fn">FastAPI</span>(title=<span class="str">"User Service"</span>)</div>',
                '<div class="code-line"><span class="ln">6</span><span class="var">cache</span> = <span class="var">redis</span>.<span class="fn">Redis</span>(host=<span class="str">"localhost"</span>, port=<span class="num">6379</span>)</div>',
                '<div class="code-line"><span class="ln">7</span></div>',
                '<div class="code-line"><span class="ln">8</span></div>',
                '<div class="code-line"><span class="ln">9</span><span class="kw">class</span> <span class="type">UserCreate</span>(BaseModel):</div>',
                '<div class="code-line"><span class="ln">10</span>    <span class="var">email</span>: <span class="type">str</span></div>',
                '<div class="code-line"><span class="ln">11</span>    <span class="var">name</span>: <span class="type">str</span></div>',
                '<div class="code-line"><span class="ln">12</span>    <span class="var">role</span>: <span class="type">str</span> = <span class="str">"member"</span></div>',
                '<div class="code-line"><span class="ln">13</span></div>',
                '<div class="code-line"><span class="ln">14</span></div>',
                '<div class="code-line"><span class="ln">15</span><span class="cm"># TODO: add rate limiting</span></div>',
                '<div class="code-line"><span class="ln">16</span>@<span class="fn">app.post</span>(<span class="str">"/users"</span>)</div>',
                '<div class="code-line"><span class="ln">17</span><span class="kw">async def</span> <span class="fn">create_user</span>(<span class="var">user</span>: <span class="type">UserCreate</span>):</div>',
                '<div class="code-line"><span class="ln">18</span>    <span class="cm"># Check cache first</span></div>',
                '<div class="code-line"><span class="ln">19</span>    <span class="kw">if</span> cache.<span class="fn">exists</span>(f<span class="str">"user:{user.email}"</span>):</div>',
                '<div class="code-line"><span class="ln">20</span>        <span class="kw">raise</span> <span class="fn">HTTPException</span>(<span class="num">409</span>, <span class="str">"User already exists"</span>)</div>',
                '<div class="code-line"><span class="ln">21</span></div>',
                '<div class="code-line"><span class="ln">22</span>    <span class="var">db_user</span> = <span class="kw">await</span> <span class="var">db</span>.<span class="fn">create</span>(user.<span class="fn">dict</span>())</div>',
                '<div class="code-line"><span class="ln">23</span>    cache.<span class="fn">setex</span>(f<span class="str">"user:{user.email}"</span>, <span class="num">3600</span>, <span class="var">db_user</span>.id)</div>',
                '<div class="code-line"><span class="ln">24</span>    <span class="kw">return</span> {<span class="str">"id"</span>: <span class="var">db_user</span>.id, <span class="str">"status"</span>: <span class="str">"created"</span>}</div>',
            ]),
        },
        {
            "tabs": ["Dashboard.tsx", "api.ts", "index.css"], "active_tab": "Dashboard.tsx",
            "files": ["App.tsx", "Dashboard.tsx", "Sidebar.tsx", "api.ts", "types.ts", "index.css"],
            "branch": "feat/dashboard", "cursor_line": 18, "cursor_col": 42, "language": "TypeScript React",
            "code_lines": "\n".join([
                '<div class="code-line"><span class="ln">1</span><span class="kw">import</span> { <span class="var">useState</span>, <span class="var">useEffect</span> } <span class="kw">from</span> <span class="str">"react"</span>;</div>',
                '<div class="code-line"><span class="ln">2</span><span class="kw">import</span> { <span class="type">MetricCard</span> } <span class="kw">from</span> <span class="str">"./components"</span>;</div>',
                '<div class="code-line"><span class="ln">3</span><span class="kw">import</span> { <span class="fn">fetchMetrics</span> } <span class="kw">from</span> <span class="str">"./api"</span>;</div>',
                '<div class="code-line"><span class="ln">4</span></div>',
                '<div class="code-line"><span class="ln">5</span><span class="kw">export function</span> <span class="fn">Dashboard</span>() {</div>',
                '<div class="code-line"><span class="ln">6</span>  <span class="kw">const</span> [<span class="var">metrics</span>, <span class="fn">setMetrics</span>] = <span class="fn">useState</span>&lt;<span class="type">Metric</span>[]&gt;([]);</div>',
                '<div class="code-line"><span class="ln">7</span>  <span class="kw">const</span> [<span class="var">loading</span>, <span class="fn">setLoading</span>] = <span class="fn">useState</span>(<span class="kw">true</span>);</div>',
                '<div class="code-line"><span class="ln">8</span>  <span class="kw">const</span> [<span class="var">error</span>, <span class="fn">setError</span>] = <span class="fn">useState</span>&lt;<span class="type">string</span> | <span class="type">null</span>&gt;(<span class="kw">null</span>);</div>',
                '<div class="code-line"><span class="ln">9</span></div>',
                '<div class="code-line"><span class="ln">10</span>  <span class="fn">useEffect</span>(() =&gt; {</div>',
                '<div class="code-line"><span class="ln">11</span>    <span class="fn">fetchMetrics</span>()</div>',
                '<div class="code-line"><span class="ln">12</span>      .<span class="fn">then</span>(<span class="fn">setMetrics</span>)</div>',
                '<div class="code-line"><span class="ln">13</span>      .<span class="fn">catch</span>((<span class="var">e</span>) =&gt; <span class="fn">setError</span>(<span class="var">e</span>.message))</div>',
                '<div class="code-line"><span class="ln">14</span>      .<span class="fn">finally</span>(() =&gt; <span class="fn">setLoading</span>(<span class="kw">false</span>));</div>',
                '<div class="code-line"><span class="ln">15</span>  }, []);</div>',
                '<div class="code-line"><span class="ln">16</span></div>',
                '<div class="code-line"><span class="ln">17</span>  <span class="kw">if</span> (<span class="var">loading</span>) <span class="kw">return</span> &lt;<span class="type">Skeleton</span> /&gt;;</div>',
                '<div class="code-line"><span class="ln">18</span>  <span class="kw">if</span> (<span class="var">error</span>) <span class="kw">return</span> &lt;<span class="type">ErrorBanner</span> <span class="var">message</span>={<span class="var">error</span>} /&gt;;</div>',
                '<div class="code-line"><span class="ln">19</span></div>',
                '<div class="code-line"><span class="ln">20</span>  <span class="kw">return</span> (</div>',
                '<div class="code-line"><span class="ln">21</span>    &lt;<span class="type">div</span> <span class="var">className</span>=<span class="str">"grid grid-cols-4 gap-4"</span>&gt;</div>',
                '<div class="code-line"><span class="ln">22</span>      {<span class="var">metrics</span>.<span class="fn">map</span>((<span class="var">m</span>) =&gt; &lt;<span class="type">MetricCard</span> <span class="var">key</span>={<span class="var">m</span>.id} {...<span class="var">m</span>} /&gt;)}</div>',
                '<div class="code-line"><span class="ln">23</span>    &lt;/<span class="type">div</span>&gt;</div>',
                '<div class="code-line"><span class="ln">24</span>  );</div>',
                '<div class="code-line"><span class="ln">25</span>}</div>',
            ]),
        },
    ]
    return [(f"code/code-{i+1:02d}.png", CODE_EDITOR.render(**c)) for i, c in enumerate(codes)]


def gen_confirmations():
    confirms = [
        {"tab_title": "Verify your email", "url": "accounts.google.com/verify",
         "icon": "✓", "icon_class": "icon-success", "title": "Check your email",
         "subtitle": "We sent a verification code to s****n@gmail.com",
         "code": "847 291", "details": None, "button_text": "Open Gmail", "timer_text": "Code expires in 9:42"},
        {"tab_title": "Booking Confirmed — Airbnb", "url": "airbnb.com/trips/confirmation",
         "icon": "✓", "icon_class": "icon-success", "title": "Booking Confirmed!",
         "subtitle": "Your stay in San Francisco is all set.",
         "code": None, "details": [
             {"label": "Check-in", "value": "Mar 15, 2026"},
             {"label": "Check-out", "value": "Mar 18, 2026"},
             {"label": "Guests", "value": "2 adults"},
             {"label": "Confirmation", "value": "#HM8X92KL"},
             {"label": "Total", "value": "$487.00"},
         ], "button_text": "View Booking Details", "timer_text": None},
        {"tab_title": "Two-Factor Authentication", "url": "github.com/sessions/two-factor",
         "icon": "🔐", "icon_class": "icon-info", "title": "Two-factor authentication",
         "subtitle": "Enter the 6-digit code from your authenticator app.",
         "code": "493 817", "details": None, "button_text": "Verify", "timer_text": "Having trouble? Use a recovery code"},
        {"tab_title": "Payment Successful — Shopify", "url": "checkout.shopify.com/receipt",
         "icon": "✓", "icon_class": "icon-success", "title": "Payment Successful",
         "subtitle": "Your order has been placed and is being processed.",
         "code": None, "details": [
             {"label": "Order", "value": "#SH-29847"},
             {"label": "Items", "value": "3 items"},
             {"label": "Total", "value": "$127.48"},
             {"label": "Payment", "value": "Visa ending in 4242"},
             {"label": "Delivery", "value": "Feb 10-12, 2026"},
         ], "button_text": "Track Order", "timer_text": None},
        {"tab_title": "Email Changed", "url": "myaccount.google.com/security",
         "icon": "⚠", "icon_class": "icon-warning", "title": "Security alert",
         "subtitle": "The email address for your account was recently changed. If this wasn't you, please secure your account immediately.",
         "code": None, "details": [
             {"label": "Changed to", "value": "new****@gmail.com"},
             {"label": "When", "value": "Feb 6, 2026 at 3:42 PM"},
             {"label": "Device", "value": "MacBook Pro — Chrome"},
             {"label": "Location", "value": "San Francisco, CA"},
         ], "button_text": "Review Activity", "timer_text": None},
    ]
    return [(f"confirmations/confirm-{i+1:02d}.png", CONFIRMATION_PAGE.render(**c)) for i, c in enumerate(confirms)]


def gen_settings():
    settings = [
        {
            "window_title": "System Settings", "page_title": "Notifications",
            "active_item": "Notifications",
            "sidebar_items": [
                {"name": "General", "color": "#86868b", "icon": "⚙"},
                {"name": "Appearance", "color": "#007aff", "icon": "🎨"},
                {"name": "Notifications", "color": "#ff3b30", "icon": "🔔"},
                {"name": "Sound", "color": "#ff9500", "icon": "🔊"},
                {"name": "Focus", "color": "#5856d6", "icon": "🌙"},
                {"name": "Screen Time", "color": "#5856d6", "icon": "⏱"},
                {"name": "Privacy & Security", "color": "#007aff", "icon": "🔒"},
            ],
            "groups": [
                {"title": "Notification Style", "rows": [
                    {"label": "Show notifications on lock screen", "type": "toggle", "value": True},
                    {"label": "Allow notifications when mirroring", "type": "toggle", "value": False},
                    {"label": "Notification grouping", "type": "select", "value": "Automatic"},
                ]},
                {"title": "App Notifications", "rows": [
                    {"label": "Messages", "desc": "Banners, Sounds, Badges", "type": "toggle", "value": True},
                    {"label": "Mail", "desc": "Banners, Badges", "type": "toggle", "value": True},
                    {"label": "Slack", "desc": "Banners, Sounds, Badges", "type": "toggle", "value": True},
                    {"label": "Calendar", "desc": "Alerts, Sounds", "type": "toggle", "value": True},
                    {"label": "Reminders", "desc": "Banners, Badges", "type": "toggle", "value": False},
                ]},
            ],
        },
        {
            "window_title": "System Settings", "page_title": "Privacy & Security",
            "active_item": "Privacy & Security",
            "sidebar_items": [
                {"name": "General", "color": "#86868b", "icon": "⚙"},
                {"name": "Appearance", "color": "#007aff", "icon": "🎨"},
                {"name": "Notifications", "color": "#ff3b30", "icon": "🔔"},
                {"name": "Sound", "color": "#ff9500", "icon": "🔊"},
                {"name": "Focus", "color": "#5856d6", "icon": "🌙"},
                {"name": "Screen Time", "color": "#5856d6", "icon": "⏱"},
                {"name": "Privacy & Security", "color": "#007aff", "icon": "🔒"},
            ],
            "groups": [
                {"title": "Privacy", "rows": [
                    {"label": "Location Services", "type": "toggle", "value": True, "desc": "Allow apps to request your location"},
                    {"label": "Analytics & Improvements", "type": "toggle", "value": False, "desc": "Share analytics with Apple"},
                    {"label": "Apple Advertising", "type": "toggle", "value": False, "desc": "Personalized ads"},
                ]},
                {"title": "Security", "rows": [
                    {"label": "FileVault", "type": "text", "value": "On", "desc": "Disk encryption is enabled"},
                    {"label": "Firewall", "type": "toggle", "value": True, "desc": "Block incoming connections"},
                    {"label": "Lockdown Mode", "type": "toggle", "value": False, "desc": "Extreme protection for targeted attacks"},
                ]},
            ],
        },
    ]
    return [(f"settings/settings-{i+1:02d}.png", SETTINGS_APP.render(**s)) for i, s in enumerate(settings)]


async def main():
    all_screenshots: list[tuple[str, str]] = []
    all_screenshots.extend(gen_errors())
    all_screenshots.extend(gen_terminals())
    all_screenshots.extend(gen_receipts())
    all_screenshots.extend(gen_dashboards())
    all_screenshots.extend(gen_chats())
    all_screenshots.extend(gen_code())
    all_screenshots.extend(gen_confirmations())
    all_screenshots.extend(gen_settings())

    print(f"Generating Merlian demo dataset...")
    print(f"Will generate {len(all_screenshots)} screenshots across 8 categories.\n")

    # Ensure directories
    for cat in ["errors", "terminal", "receipts", "dashboards", "messaging", "code", "confirmations", "settings"]:
        (OUTPUT_DIR / cat).mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        for filename, html in all_screenshots:
            await page.set_content(html, wait_until="networkidle")
            await page.wait_for_timeout(200)
            out_path = OUTPUT_DIR / filename
            await page.screenshot(path=str(out_path), full_page=False)
            print(f"  {filename}")

        await browser.close()

    print(f"\nDone! {len(all_screenshots)} screenshots saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
