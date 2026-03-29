# Browser QA flow for app.tundralis.com

Use this when validating the live app through the Windows browser node.

## Auth

Local source of truth for automation:
- `secrets/.env.local`

Load secrets into a command:

```bash
./scripts/load-local-secrets.sh env | grep TUNDRALIS_BASIC_AUTH
```

For direct authenticated browser navigation, the current working pattern is embedding basic auth in the URL:

```text
https://<user>:<pass>@app.tundralis.com
```

## What is currently confirmed

As of 2026-03-29:
- Windows browser node can attach to Chrome successfully.
- Direct authenticated navigate works.
- Live DOM snapshot works after authenticated navigate.
- The live app shell loads with title `tundralis · KDA upload`.

## What is currently flaky

The issue appears to be browser-proxy/tooling reliability, not app auth itself.

Observed flaky operations on the Windows node browser proxy:
- screenshot requests timing out
- click actions timing out
- file upload path resolution requiring a Windows-local OpenClaw uploads directory

This means:
- authenticated page-load verification is trustworthy
- full end-to-end live upload automation is not yet trustworthy from the current node/browser proxy path

## Recommended live QA sequence

1. Start/confirm Windows Chrome is attached via OpenClaw browser status.
2. Navigate with embedded basic auth.
3. Use snapshot to confirm the real page title/headings loaded.
4. If upload/click automation fails, treat that as a node browser tooling issue unless the app also fails in a manual browser session.
5. For manual fallback, perform the upload in the visible Windows browser and then use snapshots to inspect the resulting mapping page.

## Next debugging target

If we want reliable automation here, debug the Windows browser proxy path separately from Tundralis:
- screenshot timeout behavior
- click/action timeout behavior
- Windows-local upload staging path for `browser upload`
