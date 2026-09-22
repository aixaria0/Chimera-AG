# Chimera Command: local UI deployment

The Lovable project `629dfe79-7b3b-4aff-80f1-7fd137576210` has a separate static frontend export. The Python backend must be the **same loopback origin** as the UI. The hosted Lovable preview cannot invoke this operator-local backend.

## Export the existing Lovable project

In the existing Lovable project, export/download its source using your authorized project workflow. From that source checkout:

```sh
bun install
bun run build:static
```

The resulting static site is `dist/client/` (NOT `dist/server/`). Copy the **contents** of `dist/client/` to an operator-controlled local directory, for example `/opt/chimera-ui`. Confirm that `/opt/chimera-ui/index.html` and `/opt/chimera-ui/assets/*.js` exist.

## Run on the machine hosting Chimera

After installing Chimera-AG and configuring a working Ollama model, from the repository directory:

```sh
CHIMERA_WEB_DIST=/opt/chimera-ui CHIMERA_HOST=127.0.0.1 python -m chimera.product
```

Then open `http://127.0.0.1:8080/`. The Python server serves the built index shell, hashed static assets, favicon and robots from `CHIMERA_WEB_DIST` and the existing `/api/*` routes on the same origin. If the variable is unset, the existing bundled `web/` UI remains the default.

Do not expose the server to the public internet or host jcode behind a remote reverse proxy. The code endpoint requires explicit operator enablement, an installed real jcode binary, a trusted workspace, and a loopback same-origin request.

## Verify on the operator machine

```sh
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/api/health
curl -i http://127.0.0.1:8080/api/features
curl -i http://127.0.0.1:8080/assets/ACTUAL_HASHED_FILENAME.js
```

Use the actual hashed filename printed by the build. The shell and assets should return HTTP 200 with HTML/JavaScript content types. `/api/health` returns `status: ready` only when Ollama is available and the configured model is installed. Complete a real chat and Council request in the local UI before calling the integrated product end-to-end verified.

This GitHub integration does not automatically sync edits back into Lovable and does not itself download Lovable's generated `dist/client` artifacts. No live local-model or browser end-to-end test is implied by this document.
