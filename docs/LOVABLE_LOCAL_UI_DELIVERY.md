# Lovable Command Center: local delivery bridge

The existing Lovable project is [Chimera Command](https://lovable.dev/projects/629dfe79-7b3b-4aff-80f1-7fd137576210). Its hosted preview is deliberately disconnected from the operator's model and coding runtime. The Python API is not an authenticated public gateway. **Do not expose it or jcode on a public endpoint.**

## What this branch adds

With `CHIMERA_WEB_DIST` unset, `python -m chimera.product` serves the same bundled `web/` frontend as before. Set `CHIMERA_WEB_DIST` to an existing compiled **static client** directory with `index.html`, and the local server serves that UI on the **same origin** as `/api/health`, `/api/models`, `/api/features`, `/api/chat`, `/api/council`, and optionally `/api/code`. Compiled files are only served beneath `/assets/`; source files, dotfiles and traversal are excluded. No new network endpoint, authentication bypass, or cloud dependency is added.

The current Lovable app uses **TanStack Start SSR** (see its `vite.config.ts` and `src/server.ts`). Its normal server build is **not necessarily a static client build with an `index.html`**. Do not point `CHIMERA_WEB_DIST` at a server bundle, or assume `npm run build` creates an export suitable for this bridge. First adapt/export the UI as an actual client-only static app *and verify it generates `dist/index.html` and `dist/assets/*`*. This export has NOT been performed or tested end-to-end here; it is the next necessary step. Exporting just frontend code does not make hosted Lovable preview connect to localhost.

## Local verification once a static export exists

Run from the repository root on the operator's machine (with Ollama installed):

```bash
# An actual compiled static client directory, NOT an SSR server distribution:
test -f /absolute/path/to/chimera-ui/dist/index.html
CHIMERA_WEB_DIST=/absolute/path/to/chimera-ui/dist python -m chimera.product
```

Visit `http://127.0.0.1:8080/`. From this **same origin**, verify `/api/health`, `/api/models`, `/api/features`, then send a real chat task and examine its `reply`. Council results are reported only after the real backend finishes. Code Studio is unavailable until the operator explicitly enables and configures coding on a trusted clean workspace; it requires local loopback origin, human confirmation, and `X-Chimera-Intent: explicit-code-run`. The current bundled Docker image does **not** include exported Lovable assets; operators must separately provide a verified static build in an authorized local deployment.

## Remaining constraints

This is a delivery bridge, not a completed live integration. The hosted preview stays disconnected, no model has been run through this UI in this change, and no production deployment or automatic Git commit is enabled. The backend's current CSP is restrictive and may need targeted adjustment if a verified exported bundle uses inline styles or external resources; only relax specific directives after inspecting the emitted bundle. Never add a wildcard `connect-src` or public code-execution API. The backend code response does not yet expose an actual Git diff, so the frontend must not fabricate one.
