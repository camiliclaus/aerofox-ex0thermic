# Security

| Concern | Measure |
|---|---|
| Secrets | Model endpoints are loopback-only and use no API keys. Keep operator settings in the ignored .env file and the runtime listener private. |
| Prompt injection via documents | Retrieved text reaches the model only inside tool results; the system prompt states tool text is data; tools cannot execute commands, write files or fetch URLs |
| Fabricated output | Numbers, charts and tables only from tool results; unknown citation ids are stripped and reported; tool failures returned as errors with "do not substitute values" |
| Input limits | 4,000-character messages; 64 kB request bodies; session ids must be hex; project fields validated by Pydantic (physical ranges) |
| Abuse / cost | per-client rate limit; daily model-turn budget; turn deadline; bounded tool rounds and tokens |
| Session isolation | separate in-memory state and lock per session; artifacts only downloadable with their own session id (tested) |
| Path traversal | datasets served only from a fixed allow-list; figure paths resolved and checked (tested) |
| Browser | strict Content-Security-Policy (self only, no inline scripts), `frame-ancestors 'none'`, `nosniff`, `no-referrer`; all model/user text HTML-escaped before rendering |
| Errors | no stack traces to users; request id in every response for log tracing |
| Proxy headers | `X-Forwarded-For` trusted only when `AEROFOX_TRUST_PROXY=1` |
| Container | non-root user; only runtime files copied |
| Dependencies | few, mainstream packages; review with `pip-audit` before release (not run in this environment) |

Known limits: sessions are in memory (lost on restart); rate limiting is per process; no authentication by design (public
demo). Report issues to the team privately before public disclosure.
