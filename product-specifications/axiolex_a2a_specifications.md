# Axiolex A2A, MCP, and Internal Services Specification

## 1. Executive summary

Axiolex is the single discovery and execution boundary for enterprise capabilities. A capability may be implemented by an MCP tool, an A2A agent skill, or an internal service. To a caller, each is a discoverable tool with a stable `tool_id` and an input contract.

The caller never needs to know the provider protocol, provider endpoint, credentials, or provider task identifiers. It asks Axiolex to discover tools for a user request, selects a result by relevance and policy, and executes that result by `tool_id`.

### Product decision and reading guide

**Synchronous A2A execution is supported today.** An A2A skill is discovered as a tool, executed through `axiolex_execute_tool`, and returned as Axiolex-normalized final content in the same request.

**Asynchronous A2A is not part of the current Axiolex client contract.** Sections 5.1–5.4, 6.5, and 7 define future requirements only. They describe the generic task lifecycle Axiolex would need before it can support provider tasks that outlive an execution request. They do not add current MCP tools, SDK methods, REST endpoints, or product promises.

```text
User request
    |
    v
Axiolex discovery: ranked, authorized tools
    |
    v
Client selects a tool_id
    |
    v
Axiolex execution and task lifecycle
    |
    +-- MCP adapter
    +-- A2A adapter
    +-- internal-service adapter
    |
    v
One normalized result or one generic Axiolex task
```

This architecture gives IDE clients such as Claude and Cursor a fixed, small MCP tool surface. It also gives custom applications a single Axiolex SDK instead of requiring them to implement MCP and A2A adapters themselves.

### Ownership boundaries

| Concern | Owner | Caller responsibility |
|---|---|---|
| Provider configuration, credentials, endpoint allowlisting, and refresh | Axiolex operators | None |
| Discovery, authorization scope, ranking, and catalog freshness | Axiolex | Supply a query and permitted scope/context |
| Selecting a ranked result | Calling IDE, application, or its agent policy | Choose a `tool_id` based on relevance and local policy |
| Transport selection and provider invocation | Axiolex | None |
| MCP session state, A2A task/context IDs, internal-service implementation details | Axiolex | None |
| Normalized result, generic task status, cancellation, and input continuation | Axiolex | Use the generic Axiolex contract |
| Task-event connection, reconnection, and resume handling | Axiolex SDK | Consume normalized events |

**Boundary rule:** endpoint, transport, and provider authentication are server-side runtime metadata resolved from `tool_id`. They are never execution parameters supplied by an LLM or client.

## 2. Status and scope

### Implemented today

Axiolex already implements the following synchronous path:

- a unified catalog containing MCP tools and A2A agent skills;
- provider configuration in `source_files/mcp_providers.yaml`;
- A2A Agent Card discovery;
- conversion of every discovered A2A skill into a catalog tool;
- `axiolex_discover_tools` ranking across the catalog;
- `axiolex_execute_tool(tool_id, arguments)` dispatch through MCP and A2A adapters; and
- normalization of provider results to the Axiolex response shape.

The existing A2A adapter is described in detail in Section 6.

### Proposed addition: universal long-running task lifecycle

This specification proposes a generic Axiolex task lifecycle for providers that acknowledge work before a final result is available. It extends the existing execution contract; it does **not** expose A2A concepts to callers and does not change discovery or tool selection.

The extension is required for reliable support of long-running A2A tasks, and may also be used by MCP or internal providers with asynchronous work.

## 3. Unified capability model

Axiolex treats a **tool** as anything it can discover, authorize, and execute on behalf of a caller. This is an Axiolex product term, not a claim that the underlying provider uses the MCP tool model.

| Provider implementation | Unit indexed by Axiolex | Caller sees | Axiolex executes |
|---|---|---|---|
| MCP provider | MCP tool | A tool with `tool_id` and schema | MCP `tools/call` over the configured MCP transport |
| A2A provider | Agent Card skill | A tool with `tool_id` and prompt schema | A2A `SendMessage` to the configured agent |
| Internal service | Registered internal capability | A tool with `tool_id` and schema | The approved internal-service adapter/handler |

A result from discovery has the same selection-oriented shape regardless of its implementation:

```json
{
  "tool_id": "veris_finance_a2a:financial_research",
  "name": "Financial Research",
  "description": "Source-grounded company research.",
  "params": {
    "prompt": { "type": "string" }
  },
  "relevance_score": 0.96,
  "rank": 1
}
```

`transport: "a2a"`, the provider endpoint, and authentication are useful Axiolex runtime metadata, but not data a caller needs in order to select or invoke a tool. They may be included in trusted administrative/debug views, but must not become LLM-controlled execution inputs.

## 4. Client journeys

### 4.1 IDE clients: Claude, Cursor, and other non-native A2A clients

IDE clients register a fixed Axiolex MCP server. They do not dynamically register every discovered downstream tool and do not need an A2A adapter.

```text
User: "Research this company for me"
  |
  v
IDE model calls axiolex_discover_tools(query)
  |
  v
Axiolex returns ranked tools from MCP, A2A, and internal providers
  |
  v
IDE model selects a tool_id and calls axiolex_execute_tool(tool_id, arguments)
  |
  v
Axiolex invokes the correct provider and returns a normalized result
```

**Current behavior:** the final response is returned in the execution call. A provider that does not finish within Axiolex's configured execution timeout returns a normal normalized timeout/error; the IDE has no task handle to resume.

**Future requirement only:** if Axiolex supports long-running work, it would return a generic Axiolex task handle. The IDE would then use generic Axiolex task tools; it would never poll an A2A agent directly.

```text
axiolex_execute_tool
  -> accepted task_id
  -> axiolex_wait_for_task(task_id)
  -> completed result
```

An IDE cannot reliably receive unsolicited completion messages after a tool call has ended. It must poll or long-poll. `axiolex_wait_for_task` should wait for a bounded server-side interval and return the final result if ready; otherwise it returns the same task as still running. Tool descriptions and result text must explicitly tell the model when to call it again.

### 4.2 Custom applications using the Axiolex SDK

**Current behavior:** custom applications use the same synchronous discovery and execution contract as IDE clients. The SDK provides discovery and execution; it does not currently provide task streaming.

**Future requirement only:** the Axiolex SDK would provide the richer task experience below.

```text
Application / application agent
  -> Axiolex SDK discover(...)
  -> Axiolex SDK execute(tool_id, arguments)
  -> completed result, or task_id
  -> SDK task stream / callbacks / await helper
```

The application does not implement SSE, reconnection, A2A JSON-RPC, MCP sessions, or provider-specific state. The SDK consumes Axiolex's normalized task-event stream and exposes application-friendly APIs, for example:

```python
execution = client.execute(
    "veris_finance_a2a:financial_research",
    {"prompt": "Research Nvidia's FY2024 revenue"},
)

if execution["status"] == "success":
    use_result(execution["result"]["content"])
else:
    for event in client.tasks.stream(execution["task_id"]):
        if event["type"] == "task.completed":
            use_result(event["content"])
            break
```

The SDK is responsible for authentication, SSE heartbeat handling, reconnection, resume cursor handling, event normalization, cancellation, and submitting follow-up input. A custom application can therefore receive completion promptly while its UI and agent continue other work.

## 5. Future requirements: asynchronous task contract

**This entire section is future-state design, not implemented behavior.** Current IDE and SDK consumers use the synchronous `discover -> execute -> final result` contract in Sections 4 and 6. The following requirements apply only if Axiolex later elects to support long-running provider tasks.

### 5.1 Fixed tool surface for IDE clients

The Axiolex MCP server would expose these additional stable tools:

| Tool | Purpose | Required for |
|---|---|---|
| `list_namespaces` | Discover eligible business scopes | Existing discovery flow |
| `axiolex_discover_tools` | Return ranked execution-ready tools for a request | Existing discovery flow |
| `axiolex_execute_tool` | Execute a selected `tool_id` | Existing synchronous execution and task creation |
| `axiolex_get_task` | Return an immediate normalized task status | Proposed async lifecycle |
| `axiolex_wait_for_task` | Long-poll briefly for a normalized task result | Proposed async lifecycle |
| `axiolex_submit_task_input` | Supply requested input and resume a task | Proposed async lifecycle |
| `axiolex_cancel_task` | Request cancellation of a task | Proposed async lifecycle |

Do not require an IDE to use an A2A-specific tool, task ID, context ID, event stream, or endpoint.

`axiolex_subscribe_task_events` should not be the primary IDE contract. A normal MCP tool call is one-shot, while a subscription is persistent. IDEs should use `axiolex_get_task` and `axiolex_wait_for_task`. The subscription surface belongs to the SDK and API described in Section 5.3.

### 5.2 Execute response

`axiolex_execute_tool` preserves the current completed result shape. A future task-aware implementation would add a second successful outcome.

Completed:

```json
{
  "status": "success",
  "tool_id": "veris_finance_a2a:financial_research",
  "execution_id": "exec_123",
  "result": {
    "content": [
      { "type": "text", "text": "Nvidia's revenue in FY2024 was ..." }
    ],
    "is_error": false
  }
}
```

Accepted:

```json
{
  "status": "accepted",
  "tool_id": "veris_finance_a2a:financial_research",
  "execution_id": "exec_123",
  "task_id": "task_abc123",
  "next_action": "axiolex_wait_for_task",
  "message": "The task is running. Call axiolex_wait_for_task with task_id task_abc123 to obtain the result."
}
```

`execution_id` remains a per-call trace/audit identifier. `task_id` is an opaque, durable Axiolex handle for work that outlives the initial execution request. A caller must not receive or depend on an underlying A2A task or context ID.

### 5.3 Generic task contract

All task operations use `task_id`; no provider-specific identifier appears in their public request or response.

| Operation | Inputs | Result |
|---|---|---|
| `axiolex_get_task` | `task_id` | Current state without waiting |
| `axiolex_wait_for_task` | `task_id`, optional bounded `timeout_ms` | Completed result, input request, failure, or still-running state |
| `axiolex_submit_task_input` | `task_id`, `input` | Acknowledgement and resumed task state |
| `axiolex_cancel_task` | `task_id` | Cancellation request status |
| SDK `tasks.stream(task_id)` | `task_id` | Normalized SSE event stream |
| SDK `tasks.await_result(task_id)` | `task_id`, optional timeout | Final normalized result or current non-final state |

The API may expose the stream as an authenticated SSE endpoint, for example `GET /tasks/{task_id}/events`. The SDK is the preferred application integration surface for this endpoint.

Normalized states:

| Axiolex state | Meaning | Next caller action |
|---|---|---|
| `accepted` | Work was accepted but has not produced a final result | Wait, poll, or subscribe |
| `running` | Work is still in progress | Wait, poll, or subscribe |
| `input_required` | The provider requires a user/agent response | Submit input, then wait again |
| `completed` | Final normalized content is available | Consume the result |
| `failed` | Work ended without a result | Handle normalized error/retry guidance |
| `cancelled` | Work was cancelled | No further action |

Example input-required response:

```json
{
  "status": "input_required",
  "task_id": "task_abc123",
  "input": {
    "prompt": "Which fiscal year should I use?"
  },
  "next_action": "axiolex_submit_task_input"
}
```

Example normalized SSE event:

```json
{
  "type": "task.completed",
  "task_id": "task_abc123",
  "content": [
    { "type": "text", "text": "The company research is complete ..." }
  ]
}
```

### 5.4 Task lifecycle flow

```text
execute_tool(tool_id, arguments)
  |
  +-- completed --> normalized result
  |
  +-- accepted --> task_id
                    |
                    +-- get_task / wait_for_task --> running
                    |                                 |
                    |                                 +-- completed --> normalized result
                    |                                 +-- failed --> normalized error
                    |                                 +-- input_required
                    |                                      |
                    |                                      +-- submit_task_input --> running
                    |
                    +-- cancel_task --> cancelled
                    |
                    +-- SDK task stream --> lifecycle events
```

## 6. Current A2A implementation

### 6.1 Provider configuration

An A2A provider is configured in `source_files/mcp_providers.yaml` with `transport: a2a`:

```yaml
- id: veris_finance_a2a
  name: Veris Finance Research (A2A)
  transport: a2a
  endpoint: http://localhost:8100/agents/veris-finance-research-agent/
  auth:
    type: none
  enabled: true
  namespaces:
    - veris.research
```

The provider configuration, auth material, endpoint, timeouts, and rate limits remain Axiolex-managed runtime configuration. Callers never submit them during execution.

### 6.2 Agent Card discovery and normalization

During provider/index refresh, Axiolex fetches the Agent Card at:

```text
GET {endpoint}/.well-known/agent-card.json
```

For this provider:

```text
GET http://localhost:8100/agents/veris-finance-research-agent/.well-known/agent-card.json
```

An Agent Card skill such as:

```json
{
  "id": "financial_research",
  "name": "Financial Research",
  "description": "..."
}
```

becomes a single Axiolex catalog tool:

| Agent Card skill | Axiolex catalog tool |
|---|---|
| `id: financial_research` | `tool_id: veris_finance_a2a:financial_research` |
| `name: Financial Research` | `title/name: Financial Research` |
| `description` | `description` |
| No structured input schema | `params: { prompt: { type: string } }` |

Axiolex retains runtime metadata equivalent to:

```json
{
  "tool_name": "financial_research",
  "transport": "a2a",
  "endpoint": "http://localhost:8100/agents/veris-finance-research-agent/",
  "provider": "veris_finance_a2a",
  "auth": { "type": "none" },
  "params": { "prompt": { "type": "string" } }
}
```

This mapping lets A2A skills participate in the same ranking and selection process as MCP tools and internal capabilities.

### 6.3 Current request-scoped execution

When a caller invokes:

```text
axiolex_execute_tool(
  "veris_finance_a2a:financial_research",
  {"prompt": "What was Nvidia revenue?"}
)
```

the Axiolex A2A adapter resolves the `tool_id`, loads its server-side A2A metadata, and creates a JSON-RPC `SendMessage` request.

- If arguments contain `prompt`, Axiolex sends its value as a text part.
- Otherwise, Axiolex JSON-encodes the argument object and sends it as a text part.

```http
POST http://localhost:8100/agents/veris-finance-research-agent/
Content-Type: application/json
A2A-Version: 1.0

{
  "jsonrpc": "2.0",
  "method": "SendMessage",
  "id": 1,
  "params": {
    "message": {
      "message_id": "uuid-generated-by-axiolex",
      "role": "ROLE_USER",
      "parts": [
        {"text": "What was Nvidia revenue?"}
      ]
    }
  }
}
```

For an immediately completed A2A task, Axiolex extracts text from task artifact parts and returns its standard result:

```json
{
  "content": [
    { "type": "text", "text": "Nvidia's revenue in 2024 was $130.5B..." }
  ],
  "is_error": false
}
```

The caller sees only that normalized result. It does not know whether the tool was backed by A2A or MCP.

### 6.4 A2A and MCP differences Axiolex absorbs

| Concern | MCP | A2A | What Axiolex normalizes |
|---|---|---|---|
| Discovery | `tools/list` over an MCP connection | Agent Card at `/.well-known/agent-card.json` | Catalog tools |
| Provider unit | Tool with structured schema | Agent skill with description/input modes | A tool ID and Axiolex input contract |
| Execution | `tools/call` with structured arguments | `SendMessage` with text parts | `axiolex_execute_tool(tool_id, arguments)` |
| Provider state | MCP initialization/session behavior depends on transport | A2A tasks and contexts may span messages | Opaque Axiolex runtime/task state |
| Immediate response | `content[]` | Task artifacts/parts | Normalized `content[]` |
| Long-running work | Provider-specific | A2A task lifecycle | Proposed generic Axiolex task lifecycle |

An A2A request is request-scoped in the current Axiolex adapter: one execution call sends one message and returns the available normalized result. A2A can support longer-lived tasks and context; the proposed task lifecycle is how Axiolex should support that capability without asking callers to become A2A clients.

### 6.5 A2A wait behavior and the async adapter policy

`SendMessage` has a provider-facing execution setting named `return_immediately` in the protocol model; its JSON wire name is `returnImmediately`.

- When it is `false` or omitted, A2A's default behavior is to wait until the task reaches a terminal state (`completed`, `failed`, `cancelled`, or `rejected`) or an interrupted state (`input_required` or `auth_required`).
- When it is `true`, the agent returns after creating/acknowledging the task, allowing the caller to use the task ID for polling, streaming, cancellation, or follow-up input.

The current Axiolex request shown in Section 6.3 does not set `return_immediately`. It therefore uses the synchronous default, which is appropriate for the current fast, request-scoped path.

For the proposed generic Axiolex task lifecycle, the A2A adapter must choose non-blocking behavior **before** it sends a potentially long-running request. It cannot reliably recover an A2A task ID after a locally timed-out blocking `SendMessage` call.

Recommended policy for A2A providers configured for asynchronous execution:

```text
1. SendMessage with `configuration.returnImmediately: true`.
2. Persist Axiolex task_id and the returned A2A task/context identifiers.
3. Immediately poll or subscribe through A2A for a short Axiolex completion budget.
4. If the task finishes within that budget, return Axiolex success with normalized content.
5. Otherwise, return Axiolex accepted with the opaque task_id.
```

This preserves the one-call experience for fast A2A tasks while ensuring Axiolex has a durable handle for genuinely long-running tasks. The policy should be explicit provider/tool configuration, not an LLM-controlled execution parameter.

**Protocol compatibility note:** current A2A JSON uses camelCase field names, including `messageId`, `returnImmediately`, `acceptedOutputModes`, `historyLength`, and `pushNotificationConfig`. Axiolex must serialize according to the version and binding declared by the selected Agent Card. If a legacy/implementation-specific agent accepts snake_case fields, that compatibility behavior belongs in the A2A adapter and should be tested explicitly rather than assumed for all A2A providers.

## 7. Adapter and persistence requirements for asynchronous work

When a provider responds with work that is not final, Axiolex must create a durable task record. The record must retain, at minimum:

- opaque `task_id` owned by Axiolex;
- caller/tenant authorization binding;
- source `tool_id`, provider, and transport;
- internal provider correlation data (for example, A2A task/context identifiers);
- normalized status, timestamps, result/error state, and resume cursor; and
- expiry/retention policy appropriate to the task's sensitivity.

Only Axiolex adapters read or write the provider correlation data. The task service translates provider state to Section 5.3's normalized state machine.

Task ownership checks are mandatory on every get, wait, input, cancel, and stream operation. A task ID alone must not grant cross-user or cross-tenant access.

The existing SSE queue pattern should be reused for Axiolex task events, including heartbeat and reconnection behavior. Event delivery must support a cursor or last-event identifier so SDK reconnects do not silently lose completion or input-required events.

## 8. Documentation and contract alignment required

This document is additive to the implemented synchronous A2A path. Before publishing it as product behavior, the following documents/contracts must be aligned:

1. **`product-specifications/axiolex-execute-tool-spec.md`** — extend the response contract from only `success | error` to include accepted asynchronous work, a `task_id`, and the task-management operations. Preserve `execution_id` as a trace ID.
2. **`product-specifications/axiolex-architecture.md`** and **`product-specifications/axiolex Central Capability - Tools Discovery — Architecture Specification.md`** — update any discovery-only or direct-execution language. The product direction in this specification is centralized discovery **and execution** for both IDE and SDK clients; direct downstream provider calls are not required for normal consumption.
3. **MCP server tool definitions and instructions** — add the generic task tools with explicit descriptions that teach models the `execute -> wait -> completed` and `input_required -> submit -> wait` loops.
4. **REST API and Python SDK documentation** — specify task status endpoints and the authenticated task-event stream. The SDK, not each application, owns stream lifecycle handling.
5. **README and marketing material** — communicate one clear promise: consumers discover and execute relevant enterprise capabilities through Axiolex without implementing protocol-specific adapters.

## 9. Product message

Today, Axiolex unifies enterprise capability discovery and synchronous execution across MCP tools, A2A agent skills, and internal services. IDE clients use a fixed set of Axiolex MCP tools, and applications use the Axiolex SDK; neither needs a provider-specific adapter. A generic asynchronous task lifecycle is a documented future extension, not a current product claim.
