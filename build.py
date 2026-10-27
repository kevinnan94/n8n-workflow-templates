"""Generates the workflow JSON files in workflows/ from compact Python specs.
Run: python build.py   (also validates structure). Edit specs here, not the JSON."""
import json
from pathlib import Path

OUT = Path(__file__).parent / "workflows"


def node(name, ntype, version, params, x, y, creds=None):
    n = {"parameters": params, "name": name, "type": ntype, "typeVersion": version, "position": [x, y]}
    if creds:
        n["credentials"] = {creds: {"id": "REPLACE_ME", "name": "your credential"}}
    return n


def chain(*names):
    return {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(names, names[1:])}


def workflow(name, nodes, connections):
    return {"name": name, "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}, "active": False}


SCHEDULE_DAILY = {"rule": {"interval": [{"field": "hours", "hoursInterval": 24}]}}
TELEGRAM = lambda text: {"chatId": "={{ $env.TELEGRAM_CHAT_ID || 'REPLACE_CHAT_ID' }}", "text": text,
                         "additionalFields": {"parse_mode": "HTML", "disable_web_page_preview": True}}

RSS_DIGEST_CODE = """// Build one HTML digest from the newest RSS items. Change MAX to taste.
const MAX = 10;
const items = $input.all().slice(0, MAX);
if (!items.length) return [];
const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const lines = items.map((it, i) => `${i + 1}. <a href="${esc(it.json.link)}">${esc(it.json.title)}</a>`);
return [{ json: { text: `<b>Daily digest</b> (${items.length})\\n\\n${lines.join('\\n')}` } }];
"""

CHANGE_MONITOR_CODE = """// Keep a hash of the last seen content in workflow static data.
// Emits one item only when the content changed since the previous run.
const crypto = require('crypto');
const body = typeof $json.data === 'string' ? $json.data : JSON.stringify($json);
const hash = crypto.createHash('sha256').update(body).digest('hex');
const store = $getWorkflowStaticData('global');
const changed = store.lastHash !== undefined && store.lastHash !== hash;
const first = store.lastHash === undefined;
store.lastHash = hash;
if (first || !changed) return [];
return [{ json: { hash, checkedAt: new Date().toISOString(), preview: body.slice(0, 300) } }];
"""

RELEASE_WATCH_CODE = """// Notify once per new GitHub release (tag stored in static data).
const store = $getWorkflowStaticData('global');
const tag = $json.tag_name;
if (!tag || store.lastTag === tag) return [];
const isFirst = store.lastTag === undefined;
store.lastTag = tag;
if (isFirst) return [];
return [{ json: { tag, name: $json.name || tag, url: $json.html_url, published: $json.published_at } }];
"""

WORKFLOWS = {
    "rss-digest-telegram": workflow(
        "RSS daily digest to Telegram",
        [
            node("Every day", "n8n-nodes-base.scheduleTrigger", 1.2, SCHEDULE_DAILY, 0, 0),
            node("Read RSS", "n8n-nodes-base.rssFeedRead", 1.1, {"url": "https://hnrss.org/frontpage", "options": {}}, 220, 0),
            node("Build digest", "n8n-nodes-base.code", 2, {"jsCode": RSS_DIGEST_CODE}, 440, 0),
            node("Send to Telegram", "n8n-nodes-base.telegram", 1.2, TELEGRAM("={{ $json.text }}"), 660, 0, "telegramApi"),
        ],
        chain("Every day", "Read RSS", "Build digest", "Send to Telegram"),
    ),
    "website-change-monitor": workflow(
        "Website change monitor to Telegram",
        [
            node("Every hour", "n8n-nodes-base.scheduleTrigger", 1.2,
                 {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}}, 0, 0),
            node("Fetch page", "n8n-nodes-base.httpRequest", 4.2,
                 {"url": "https://example.com/pricing", "options": {"response": {"response": {"responseFormat": "text"}}}}, 220, 0),
            node("Changed since last run?", "n8n-nodes-base.code", 2, {"jsCode": CHANGE_MONITOR_CODE}, 440, 0),
            node("Send to Telegram", "n8n-nodes-base.telegram", 1.2,
                 TELEGRAM("=<b>Page changed</b>\n{{ $json.checkedAt }}\n\n<code>{{ $json.preview }}</code>"), 660, 0, "telegramApi"),
        ],
        chain("Every hour", "Fetch page", "Changed since last run?", "Send to Telegram"),
    ),
    "github-release-watch": workflow(
        "GitHub release watcher to Telegram",
        [
            node("Every 6 hours", "n8n-nodes-base.scheduleTrigger", 1.2,
                 {"rule": {"interval": [{"field": "hours", "hoursInterval": 6}]}}, 0, 0),
            node("Latest release", "n8n-nodes-base.httpRequest", 4.2,
                 {"url": "https://api.github.com/repos/n8n-io/n8n/releases/latest", "options": {}}, 220, 0),
            node("New release?", "n8n-nodes-base.code", 2, {"jsCode": RELEASE_WATCH_CODE}, 440, 0),
            node("Send to Telegram", "n8n-nodes-base.telegram", 1.2,
                 TELEGRAM("=<b>New release: {{ $json.name }}</b>\n{{ $json.url }}"), 660, 0, "telegramApi"),
        ],
        chain("Every 6 hours", "Latest release", "New release?", "Send to Telegram"),
    ),
}


def validate(wf):
    names = {n["name"] for n in wf["nodes"]}
    assert len(names) == len(wf["nodes"]), "duplicate node names"
    for src, c in wf["connections"].items():
        assert src in names, f"connection from unknown node {src}"
        for branch in c["main"]:
            for link in branch:
                assert link["node"] in names, f"connection to unknown node {link['node']}"
    assert any(n["type"].endswith("Trigger") for n in wf["nodes"]), "no trigger node"
    text = json.dumps(wf)
    assert "REPLACE_ME" in text or "telegramApi" not in text, "credential placeholder missing"
    for secret in ("bot", "token", "api_key"):
        assert f'"{secret}":' not in text.lower(), f"possible secret key {secret}"


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for slug, wf in WORKFLOWS.items():
        validate(wf)
        (OUT / f"{slug}.json").write_text(json.dumps(wf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("ok", slug, len(wf["nodes"]), "nodes")
