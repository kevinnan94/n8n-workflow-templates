# n8n-workflow-templates

Small, dependency-free n8n workflows you can import and run in two minutes. Each one does a single
useful thing and ends in a Telegram message. No paid nodes, no external database: state lives in
n8n's own workflow static data.

| Workflow | What it does | Trigger |
|---|---|---|
| `rss-digest-telegram` | Reads any RSS feed and sends a numbered HTML digest of the newest items | daily |
| `website-change-monitor` | Fetches a page, hashes it, notifies only when the content changed | hourly |
| `github-release-watch` | Watches a repo's latest release and notifies once per new tag | every 6 h |

## Import

1. n8n → Workflows → Import from file → pick a JSON from `workflows/`.
2. Open the Telegram node and select your Telegram credential (bot token from @BotFather).
3. Set the chat id: either define the `TELEGRAM_CHAT_ID` environment variable on your n8n instance
   or replace `REPLACE_CHAT_ID` in the node.
4. Change the URL in the HTTP/RSS node to the feed, page or repo you care about.
5. Activate the workflow.

CLI alternative: `n8n import:workflow --input=workflows/rss-digest-telegram.json`

## Notes

- `website-change-monitor` and `github-release-watch` stay silent on their first run: they need a
  baseline before they can detect a change.
- Static data persists only for **active** workflows. Manual test runs do not store it.
- Telegram messages use HTML parse mode; the digest escapes titles so odd characters do not break it.

## Development

The JSON files are generated from `build.py`, which also validates node names, connections and
that no credentials leak into the templates. Edit the specs there and run:

```bash
python build.py
```

## License

MIT
