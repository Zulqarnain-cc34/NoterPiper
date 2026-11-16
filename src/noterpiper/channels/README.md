# Channels — how notifications get delivered

A **channel** is how a notification reaches you. The engine fans a notification out to
*every* enabled channel, so you can receive on more than one at once. Each channel
satisfies the `Channel` contract: `send(notification)` and `already_sent(dedup_key, now)`.

## Shipped channels

### `NtfyChannel` — push to an ntfy topic
The default. Delivers to your [ntfy](https://ntfy.sh) topic and **de-duplicates** using
ntfy's own recent-message cache, so each notification is sent at most once per day with
no database. Configured by `NTFY_TOPIC`.

### `WebhookChannel` — POST to any URL
One channel for everything that accepts an HTTP POST: **Discord, Slack, Microsoft
Teams, Google Chat, Home Assistant, IFTTT, Zapier, or your own endpoint.** Set
`WEBHOOK_URL` (as a repo secret) to enable it.

It POSTs this JSON:

```json
{ "text": "<title>\n<body>", "content": "<title>\n<body>",
  "title": "...", "body": "...", "priority": "...", "tags": ["..."] }
```

The same human line sits under both `text` (Slack & most) and `content` (Discord), so
those render it directly; custom endpoints get the structured fields too.

> **Dedup caveat.** A plain webhook has no message cache like ntfy's, so (per the
> per-channel best-effort policy) it does **not** de-duplicate — it delivers on every
> engine run while a notification is "due". If repeats matter, keep the source's
> `window` small, or keep ntfy as your primary channel.

## Writing a new channel

A channel is one small class:

```python
class MyChannel:
    def send(self, notification) -> None: ...
    def already_sent(self, dedup_key, now) -> bool: ...   # best-effort; return False if you can't check
```

Add it to the enabled list in `scripts/run_engine.py` (usually gated on a config/secret
being present), and it starts receiving every notification. The engine never changes.
