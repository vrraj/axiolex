# `axiolex_execute_tool` — Technical Specification

## 1. Purpose and scope

`axiolex_execute_tool` is a single, generic dispatcher that executes a tool previously returned by `axiolex_discover_tools`. It exists specifically for callers that cannot dynamically register a newly discovered tool as a directly callable function in their own runtime (Section 3/4 of the architecture doc — fixed-integration clients such as Claude and Cursor). Developer-built applications with their own orchestration loop may use it optionally, or call a resolved endpoint directly; see Section 7.

This spec defines the contract only: request shape, response shape, error taxonomy, and the behavioral guarantees the implementation must provide. It intentionally does not prescribe internal implementation (queueing, connection pooling, etc.) beyond what's needed to guarantee the contract.

## 2. Design requirements: modular and independent

Two properties are load-bearing for this spec and shape every decision below:

- **Modular** — the tool must not be hardcoded to a single transport, backend type, or provider. Today's discoverable capabilities include MCP servers, REST endpoints, and (per the architecture doc) A2A endpoints. New transport types will be added later without changing the tool's external contract. This means the dispatcher needs a **transport adapter layer** internally: one execution contract in, transport-specific handling out, with the caller never needing to know which adapter ran.
- **Independent** — `axiolex_execute_tool` must not depend on `axiolex_discover_tools` having been called in the same session, the same process, or with any shared server-side state between the two calls. Every `axiolex_execute_tool` call must be fully self-contained: everything needed to execute is either in the request payload or resolvable fresh from the catalog by `tool_id` at call time. This is what makes Pattern A and Pattern B both work without coordination, and what lets the tool be evaluated, tested, and load-tested in isolation from discovery.

A direct implication of independence: **do not design this as "replay the last discovery result."** The caller must pass enough identifying and argument information on every call for the dispatcher to resolve the target tool from scratch, even if `axiolex_discover_tools` was never called in this session (e.g., a caller that already knows a `tool_id` from a prior session, a cached catalog, or out-of-band knowledge).

## 3. Request contract

```json
{
  "tool_id": "string, required",
  "arguments": "object, required — matches the input_schema returned by axiolex_discover_tools for this tool_id",
  "idempotency_key": "string, optional",
  "timeout_ms": "integer, optional, default: dispatcher-configured ceiling",
  "auth_context": "object, injected by the calling layer — never supplied by the LLM"
}
```

**`tool_id`** — the stable identifier returned by `axiolex_discover_tools` (not the raw tool name, which is not guaranteed unique across providers — see the naming-collision discussion in the architecture doc, Section 6). This is the only required linkage back to discovery; everything else the dispatcher needs (endpoint, transport, provider, namespace) is resolved server-side from `tool_id` against the current catalog, not trusted from the caller. This is the mechanism that satisfies "independent" — the caller doesn't carry transport details, so a provider changing its endpoint or transport doesn't require any caller-side change.

**`arguments`** — the parameters for the underlying tool call, matching the schema the discovery response advertised. Validated against the *current* schema at execution time (Section 5), not against whatever schema the caller may have cached from an earlier discovery call — this is what keeps execution correct even when a tool's contract changed between discovery and execution.

**`idempotency_key`** — optional, caller-supplied. Recommended for any tool with side effects (order creation, record updates). See Section 6.

**`auth_context`** — **never supplied by the LLM.** This must be injected by the calling application/gateway layer from the authenticated session, the same way `axiolex_discover_tools`'s authorization scoping works (architecture doc, Section 4). If the LLM could set or influence this field, namespace/tool visibility restrictions would be trivially bypassable by construction. Keep this out of the tool's LLM-facing parameter schema entirely — it should be attached to the request by the client/gateway infrastructure, not exposed as something the model fills in.

## 4. Response contract

```json
{
  "status": "success | error",
  "result": "object — present when status = success, shape defined by the underlying tool",
  "error": {
    "code": "string — see Section 8 taxonomy",
    "message": "string — human-readable, safe to show the caller",
    "retryable": "boolean"
  },
  "tool_id": "string — echoed back for correlation",
  "execution_id": "string — unique per call, for tracing/audit (Section 9)"
}
```

Always echo `tool_id` and a fresh `execution_id`, on both success and error paths — this is what makes multi-call agent loops (the discover→execute→discover pattern from the architecture doc, Section 7) traceable without the caller needing to track correlation manually.

## 5. Execution flow

1. **Resolve.** Look up `tool_id` in the current catalog. If not found (retired, never existed, or catalog changed since discovery) → `TOOL_NOT_FOUND`, not a generic failure. This is the direct payoff of the "no stale registries" governance benefit — a caller executing a `tool_id` that was retired an hour ago gets an explicit, actionable error, not a silent failure against a dead endpoint.
2. **Authorize.** Check `auth_context` against the resolved tool's namespace/sensitivity requirements. Fail closed → `UNAUTHORIZED`, before any argument validation, endpoint call, or leakage of what the tool would have done.
3. **Validate.** Validate `arguments` against the tool's *current* input schema (not a schema the caller may have cached). Fail → `INVALID_ARGUMENTS`, with enough detail in `error.message` to say which field failed, without echoing back secrets if any argument was itself sensitive.
4. **Dispatch via transport adapter.** Route to the correct adapter based on the resolved tool's transport type (MCP, REST, A2A, ...). This is the modularity boundary — see Section 10.
5. **Execute with timeout.** Enforce `timeout_ms` (or the dispatcher default). A timeout is `UPSTREAM_TIMEOUT`, distinct from an upstream error response, since retry logic differs for the two (Section 6).
6. **Normalize and return.** Map the adapter's raw result into the response contract in Section 4, regardless of what shape the underlying transport returned natively.

## 6. Idempotency and retries

- Tools that mutate state (create, update, cancel) should be called with an `idempotency_key`. The dispatcher should de-duplicate repeat calls with the same key within a bounded window (recommend: 24h) and return the original result rather than re-executing — this matters specifically for agent loops that may retry a call after an ambiguous timeout without knowing whether the first attempt actually landed.
- `retryable: true` should only be set for genuinely transient failures (timeout, upstream 5xx, rate limit) — never for `INVALID_ARGUMENTS`, `UNAUTHORIZED`, or `TOOL_NOT_FOUND`, since retrying those wastes a round-trip on a failure that won't change without caller-side correction.
- The dispatcher itself should not silently auto-retry on the caller's behalf by default — surface the retryable failure and let the calling layer (which has better context on whether retrying is safe for this specific action) decide. Auto-retry, if offered, should be opt-in per call, not baked into default behavior for anything that isn't read-only.

## 7. Pattern A vs. Pattern B usage

- **Pattern A (fixed-integration clients).** `axiolex_execute_tool` is the only path to execution. The client calls `axiolex_discover_tools`, gets a `tool_id` and schema, has the LLM produce `arguments`, and calls `axiolex_execute_tool` with that `tool_id` and those `arguments`. `auth_context` is injected by whatever gateway sits between the client and Axiolex.
- **Pattern B (developer-orchestrated).** The developer may call `axiolex_execute_tool` for the governance/audit benefit of routing through Axiolex, or may take the `endpoint`/transport info from the `axiolex_discover_tools` response and call it directly, bypassing this tool. Both are valid; document this as a genuine choice, not an oversight, so a Pattern B developer doesn't assume `axiolex_execute_tool` is mandatory plumbing.

## 8. Error taxonomy

| Code | Meaning | Retryable |
|---|---|---|
| `TOOL_NOT_FOUND` | `tool_id` doesn't resolve in the current catalog (never existed, or retired since discovery) | No |
| `UNAUTHORIZED` | `auth_context` doesn't permit this tool/namespace | No |
| `INVALID_ARGUMENTS` | `arguments` fails schema validation against the current contract | No |
| `UPSTREAM_TIMEOUT` | Underlying call exceeded `timeout_ms` | Yes |
| `UPSTREAM_ERROR` | Underlying tool/transport returned an error | Depends — set per actual upstream status |
| `RATE_LIMITED` | Dispatcher or upstream rate limit hit | Yes |
| `INTERNAL_ERROR` | Dispatcher-side failure unrelated to the above | Yes |

Keeping this taxonomy stable across all transport types (Section 10) is part of the modularity guarantee — a caller handling errors shouldn't need transport-specific error handling logic.

## 9. Observability

Every call should log, at minimum: `execution_id`, `tool_id`, resolved namespace, caller identity (from `auth_context`), timestamp, status, and latency. This is the direct enforcement mechanism for the governance case made in the architecture doc — centralized execution is only a governance win if it's actually centrally logged. Argument and result payloads should be logged subject to the same sensitivity rules as the tools themselves (don't log a payload the tool's own namespace/sensitivity classification would restrict).

## 10. Transport adapter layer (the modularity boundary)

Internally, the dispatcher should be structured as a thin, stable outer contract (Sections 3–4) over a set of interchangeable adapters, one per transport type:

```
axiolex_execute_tool (stable external contract)
        │
        ▼
  resolve tool_id → transport_type
        │
        ▼
 ┌──────────────┬──────────────┬──────────────┬─────────────┐
 │  MCP adapter │ REST adapter │ A2A adapter  │ (future...) │
 └──────────────┴──────────────┴──────────────┴─────────────┘
```

Each adapter's job is narrow: take the resolved endpoint + validated arguments, make the actual call in whatever shape that transport requires, and normalize the raw result/error back into the Section 4/8 contracts. Adding a new transport type later means writing a new adapter behind this boundary — it should never require a change to the external request/response contract, and it should never require calling clients (Claude, Cursor, developer applications) to change anything about how they call `axiolex_execute_tool`. This is what "modular" means operationally, not just as a design value: new capability types are addable without a breaking change to every integrated caller.
