# Run and share AeroFox

## Windows and the team repository

Run START_AEROFOX.bat. It starts pinned independent inference, loads the bundled NASA snapshot and opens the browser. The first setup downloads the Python packages and the model. See MODEL_RUNTIME.md for software, provenance and the reproducible alternate-OS commands. The inference process listens only on 127.0.0.1:8793.

Use an empty team-owned Git repository. Import the extracted source with git init, git add and git commit if needed. Share the archive and checksum with collaborators. Open a branch for an edit, review changes, run pytest and a real-model smoke test, and use a pull request. Keep previous release tags for rollback. Keep weights, secrets and scratch caches outside Git.

## Temporary judge access

Run a separate public-demo instance and share its temporary HTTPS URL only while you supervise the session. Use a local browser signed out from team accounts to smoke-test the generated URL, a notebook-independent NASA lookup, a Moon-to-Mars visual, and a measured CSV. Keep the inference endpoint private.

    $env:AEROFOX_PUBLIC_DEMO='1'
    python scripts/launch.py --port 8012 --no-browser

In another PowerShell window, with the official cloudflared client installed:

    powershell -ExecutionPolicy Bypass -File .\scripts\share_demo.ps1 -Cloudflared cloudflared -Port 8012

Confirm the app is actually on port 8012. Share the resulting HTTPS URL directly with judges. Keep Windows awake, the app and tunnel terminals running, and use synthetic project data. Close the tunnel after judging. Quick Tunnels have no account requirement, use random URLs, do not support SSE and have a 200 in-flight service limit. The app uses ordinary JSON responses with a much smaller model queue. Public demo mode disables conversation snapshots and interactive API documentation. Treat the URL as public during its life. A team-owned named Cloudflare Tunnel can provide a stable address if the team already has a Cloudflare-managed domain.

[Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) · [Cloudflare Tunnel setup](https://developers.cloudflare.com/tunnel/get-started/)

ZeroGPU depends on the owner's hosting eligibility and user GPU quota. Colab sessions are ephemeral and neither is required for AeroFox. The project uses the team's host and bundled evidence during the judged demo. A public hosted endpoint, an external network route, or a signed-out app check needs its own verification at the time of deployment.

[Hugging Face ZeroGPU documentation](https://huggingface.co/docs/hub/spaces-zerogpu)

