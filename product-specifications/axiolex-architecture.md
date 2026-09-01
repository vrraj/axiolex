# Axiolex: Capability Discovery for Enterprise AI Clients

## 1. The problem, in numbers

An AI client connected to 20 MCP servers with 10 tools each may have 200 tool definitions loaded before a single user request arrives. If those schemas average 200–300 tokens each (name, description, input schema, examples), tool definitions alone consume roughly 40,000–60,000 tokens of context — before the user's question, conversation history, or retrieved data are added. This is not a hypothetical extreme: Anthropic's own documentation of this problem cites a working example of 58 tools consuming approximately 55,000 tokens, and notes token consumption exceeding 134,000 tokens before optimization in cases it has observed directly.

This has three compounding effects, independent of any single vendor's model quality:

- **Token cost.** Every turn re-sends the full tool catalog if the client doesn't cache it, or the catalog occupies a fixed floor of the context window for the session if it does.
- **Selection accuracy degrades with catalog size.** Anthropic's own documentation states that tool-selection accuracy degrades once a catalog exceeds roughly 30–50 available tools, and attributes the most common failures — wrong tool selection and incorrect parameters — specifically to cases where tools have similar names (its own example: `notification-send-user` versus `notification-send-channel`). Independently developed enterprise tools can have overlapping names, descriptions, and parameter contracts, particularly when multiple teams expose similar business operations without a shared naming authority coordinating across them — the exact condition that produces this failure mode at scale.
- **Governance has no natural point of enforcement.** If every tool a company owns is visible to every client and every user by default, "who is allowed to see or call what" becomes a property you'd need to enforce per-tool, per-client, retroactively — rather than a property of a catalog that was scoped correctly in the first place.

Axiolex addresses this by separating **capability discovery** from **capability execution**, and by scoping discovery to the smallest relevant set of tools for a given request rather than exposing an entire enterprise catalog to every client, every time.

## 2. What a request looks like

Axiolex represents enterprise capabilities — tools, MCP services, A2A endpoints, internal services — as a searchable catalog, organized into namespaces that mirror how most enterprises are already organized: by business domain.

| Query | Search scope |
|---|---|
| "Show which business units have the largest variance between forecast and actual revenue." | `finance` |
| "Check whether the Micron NDA covers product evaluation." | `legal` |
| "Show engineering roles that have remained unfilled for more than 60 days." | `hr.recruiting` |
| "What health insurance options are available for dependents?" | `hr.employee_services` |
| "Explain what is driving the predicted supplier lead time up for `SAMSUNG_HBM3e_LINES`." | `supply_chain` |
| "Which deals expected to close this quarter are still waiting for contract approval?" | `sales`, `legal` |

The first five map to a single, unambiguous namespace. The sixth is different in kind: it's one business question whose answer depends on capabilities from two domains, not two separate questions bundled together. That distinction — between a single intent spanning multiple domains and multiple genuinely independent intents — turns out to matter for how discovery has to be called, and is worth making precise before going further (Section 7).

In each case, the calling application or AI client doesn't need to know in advance which of the company's hundreds of tools might answer the question, who owns them, or where they're deployed. It asks Axiolex, gets back a small, relevant set, and proceeds from there.

## 3. Two layers: discovery and execution

Axiolex's contract is deliberately narrow. It answers one question — *given this query and these optional scope constraints, which capabilities are relevant?* — and returns tool names, descriptions, parameter schemas, and endpoints. It does not execute anything by itself.

This creates two distinct layers, and the distinction matters differently depending on what kind of client is asking.

**AI-native applications built directly on MCP** — internal agentic apps, copilots built by the enterprise itself — can close the loop in one step: call Axiolex's discovery endpoint, take the returned MCP endpoint, and connect to or invoke it directly. For these applications, the two layers are not really a problem, because the application controls its own execution path end to end.

**Fixed-integration clients — Claude, Cursor, and similar — are a different case.** These clients connect to a defined set of MCP servers at session initialization, and load each server's tool definitions at that time. A discovery call to Axiolex returns information about a tool — its name, schema, endpoint — as data in a tool result. That data does not, by itself, register as a new callable tool for the rest of the session. The client can *read* that a tool called `get_stock_price_history` exists and what it expects as input, but has no `tool_use` capability pointing at it, because it was never part of the client's tool list at connection time.

For these clients, the fix is a **generic execution tool**, exposed by Axiolex itself: `axiolex_execute_tool(tool_id, arguments)`. Critically, the model is never given `endpoint`, `method`, or transport details as a parameter it controls — only the stable `tool_id` a prior `axiolex_discover_tools` call returned, plus the arguments for that specific tool's schema. Axiolex resolves the endpoint, transport, and authentication from its own catalog at execution time, server-side. If the model could specify the target endpoint directly, Axiolex would become a generic network dispatcher that executes wherever it's told — a real security exposure, since a manipulated tool description or an injected instruction could redirect a call to an arbitrary destination. Constraining the model to a `tool_id` it can only have obtained from a prior, legitimate discovery call closes that off: nothing can be executed that wasn't already vetted and catalogued by Axiolex first. The client only ever needs two fixed, statically-registered tools — `axiolex_discover_tools` and `axiolex_execute_tool` — regardless of how many hundreds of underlying capabilities the enterprise adds, removes, or renames over time. Discovery finds the capability and its contract; execution is a single, stable interface the client already has, that Axiolex resolves server-side into the actual call against the actual backend.

This closes the gap without requiring any change to how Claude, Cursor, or similar clients handle tool registration — the "dynamic" part of the system is hidden behind a static interface both already support.

## 4. The execution contract: when `axiolex_execute_tool` is required, and when it's optional

The generic execution tool introduced in Section 3 is not a single mandatory interface for every kind of caller. Its role differs by client category, and the documentation needs to state this explicitly rather than let it be assumed.

**Naming.** MCP does not define a standard generic-dispatcher pattern to converge on — its own mechanism is direct per-tool registration (`tools/list` + `tools/call` against a specific, known tool), which is the exact constraint this pattern works around. There is no external convention being deviated from. What matters more than matching a nonexistent standard is avoiding collision with the names of tools Axiolex itself discovers — a dispatcher named `execute` or `run` is one lexical accident away from colliding with a discovered tool named `execute_job` or `run_pipeline`, reintroducing the exact ambiguity namespaces exist to prevent at the tool level. A prefixed, layer-identifying name (`axiolex_execute_tool`, consistent with how discovery is exposed) is preferable to a bare generic verb, and the tool's description — stating plainly that it should only be called with a `tool_id` and arguments already returned by a prior `axiolex_discover_tools` call — does more to constrain correct use than the name choice does on its own.

**Parameter surface.** The model-facing parameters are `tool_id` and `arguments` only — never `endpoint`, `method`, or any other transport detail. This is a security boundary, not a convenience choice: if the model could specify the destination directly, Axiolex would function as a generic network dispatcher willing to call wherever it's told, and a manipulated tool description or an injected instruction could redirect execution to an arbitrary destination. Restricting the model to a `tool_id` — a handle it can only have obtained from a legitimate prior `axiolex_discover_tools` call — means nothing can be executed that Axiolex didn't already resolve, catalogue, and authorize itself. It also directly serves the lifecycle argument from Section 8: if a tool's underlying endpoint changes tomorrow, the caller's `tool_id` doesn't change, and the caller has no reason to notice.

**Pattern A — clients that cannot dynamically register newly discovered capabilities mid-session.** Claude, Cursor, and similar agents connect to a defined tool set at session initialization; today, none of them can take a tool discovered mid-conversation and register it as a directly callable function for the remainder of that session (Section 3). For clients with this constraint, `axiolex_discover_tools` and `axiolex_execute_tool` together provide the stable execution path — Axiolex acts as both discovery layer and execution proxy, because the calling platform gives it no other option today. This is a statement about the current constraint these clients operate under, not a permanent architectural fact about them; the pattern is defined by the constraint, and applies to whichever clients have it for as long as they have it.

**Pattern B — developer-built applications with their own orchestration loop.** A developer who controls the full request lifecycle — parsing user intent, calling `axiolex_discover_tools`, constructing the `tools` array passed to the LLM API call, and receiving the resulting `tool_use` output — already has the resolved endpoint, schema, and calling context from the discovery response by the time execution is needed. At that point, using `axiolex_execute_tool` is a convenience, not a requirement: it centralizes logging, governance, and authorization enforcement through Axiolex, but the developer is equally free to call the resolved endpoint directly, since they hold everything needed to do so without an intermediary.

The distinction matters because it prevents `axiolex_execute_tool` from being read as required plumbing for every integration. It exists because Pattern A clients currently have no alternative; Pattern B callers have a choice, and the tradeoff — centralized governance and audit trail versus one fewer network hop — is theirs to make based on their own requirements.

## 5. The catalog problem: what Axiolex actually solves that isn't being solved elsewhere

Section 1 opened with a token-cost argument, and it's a real one — but it's worth being clear-eyed that it is not the strongest or most durable case for this architecture. Token overhead from large tool catalogs is already an active, well-resourced problem in the industry: deferred/on-demand tool loading, where only a search capability loads upfront and specific tool definitions are pulled in on demand as they become relevant, is already shipping and is reported to reduce token consumption from tool definitions by over 85% in practice. That means the token argument, on its own, has a shelf life — it is being actively engineered down by model providers independent of anything Axiolex does.

What isn't being solved by deferred loading, or by any per-client tool-search mechanism, is the enterprise catalog problem itself:

- What capabilities exist across the company, in total?
- Who publishes and owns each one?
- Where is each one currently deployed, and on what transport?
- What is its current contract — parameters, schema, authentication?
- Which users or applications are allowed to discover it at all?
- How does a client execute a capability it never had preloaded?

A per-client deferred-loading mechanism searches whatever tool definitions that specific client was configured with. It has no way to answer "what does the company have that this client was never told about" — that requires a source of truth that exists independent of any one client's configuration, which is a different problem than making a known catalog cheaper to search.

This is the core of what centralizing discovery and execution through Axiolex actually buys, expressed simply:

```
Capability deployed or changed
          ↓
central catalog updated
          ↓
all Axiolex consumers discover current state
```

Once discovery and execution both run through Axiolex, tool lifecycle management stops being something every connected client needs to track independently. Without this layer, a company adding a new MCP server, renaming a tool, or changing a parameter contract has no single guaranteed way to propagate that change to already-connected clients. A client's capability view is limited to the MCP servers it knows about and to the tool-list synchronization behavior supported by those servers and the client. A newly deployed server is invisible to a client that was never configured to connect to it, regardless of any notification mechanism — that requires discovery or configuration at the client level, which is a separate problem from keeping an already-connected server's tool list current (see Section 8 for why even that narrower problem isn't fully solved by the protocol's own change-notification path).

With discovery and execution centralized in Axiolex, the enterprise makes one change — retire a tool, add a provider, update a schema — in one place, and every calling application sees the current state on its very next discovery call, with no reconnection or reinitialization required on the client side. The registry problem doesn't disappear; it moves to a single system designed to own it, instead of being duplicated (and inevitably falling out of sync) across every connected client and application. This is the answer to the six questions above that no per-client optimization addresses, no matter how good it gets at making a known catalog cheap to search.

The same centralization gives you a natural point to enforce access control: `axiolex_discover_tools` can be scoped not only by namespace but by the calling user's actual authorization, so that a request from someone without Finance access simply never surfaces Finance tools as a discovery result, rather than relying on every downstream client to independently filter what it was told.

## 6. Namespaces: why domain boundaries are the right granularity

The core design choice in Axiolex's catalog is organizing tools by business domain — `finance`, `legal`, `sales`, `hr.recruiting`, `hr.employee_services`, `supply_chain` — rather than by naming convention or by exposing a flat, ungrouped list.

The case for this rests on two things that are true of most enterprises independent of what technology they're running:

**Naming uniqueness across independently-built tools cannot be enforced.** Two teams, working without a shared registry authority, will predictably ship tools with overlapping or identical names and near-identical descriptions. Trying to solve this through naming convention discipline doesn't survive contact with a real organization of any size. Namespace scoping sidesteps the problem structurally: the namespace is the disambiguation mechanism, not the tool name.

**Most corporate structures are already domain-bounded, and the boundaries are already clear.** Finance, Legal, Sales, HR, Supply Chain, Engineering are not artificial categories invented for this system — they're how the organization is already divided, with existing ownership. Assigning a tool to one or more of these namespaces is not a difficult modeling exercise; it maps onto structure that already exists. The goal is not to build a granular, engineered tool taxonomy — a small number of well-understood domain boundaries is sufficient to eliminate the vast majority of cross-domain tool confusion, without requiring the ongoing curation overhead a fine-grained taxonomy would demand.

The benefit compounds for applications that are already domain-specific. An HR recruiting application calling `axiolex_discover_tools(namespace="hr.recruiting", query=...)` directly from its own code gets a hard boundary, not a probabilistic one — Finance and Legal tools are never surfaced, never enter context, and are never candidates for execution, because the application itself constrains the query before an LLM is ever involved in tool selection.

For general-purpose agents like Claude or Cursor, where the client doesn't know in advance which domain a user's question belongs to, namespace filtering is still available as an *optional* narrowing signal rather than a hard requirement — see Section 9 for how that inference should be treated.

## 7. Multi-scope and compound requests: two different problems that look similar

Not every query maps to a single namespace, but the queries that don't are not all the same kind of problem, and it's worth separating them before talking about how discovery should be called.

**Multi-scope request: one business intent, capabilities from multiple domains.** "Which deals expected to close this quarter are still waiting for contract approval?" is a single question. It cannot be answered without both deal-pipeline data (`sales`) and contract-approval status (`legal`), but the person asking it has one intent, not two — they want one answer that happens to require joining data from two domains.

**Compound request: multiple independently satisfiable intents.** "Show open engineering roles and summarize Q3 revenue variance" is a different shape entirely. These are two unrelated questions that happen to have been asked in the same message — one about `hr.recruiting`, one about `finance` — and each is fully answerable on its own, with no relationship between them beyond having arrived together.

The distinction matters because it changes what "getting it right" looks like. A multi-scope request has one correct combined answer; failing to retrieve either domain's tools produces an incomplete answer to the single question being asked. A compound request has two independently correct answers; failing to decompose it risks not just incomplete retrieval but the same tool-dilution problem in Section 1 — a single query blending unrelated vocabulary degrades retrieval for both intents, even though neither intent had anything to do with the other.

A tool's description represents one narrow capability. Retrieval — whether BM25, dense embeddings, or a hybrid method — scores a query against that description by term or semantic overlap. For both multi-scope and compound requests, matching the full, unsplit query as one unit against individual, narrow tool descriptions has the same structural problem: the query blends vocabulary from domains that no single tool spans, diluting the relevance signal for tools in *either* domain.

Axiolex's contract is deliberately silent on how this gets resolved: it does not decompose queries, and it does not care how many times it's called or in what order. It answers the same way every time — *given this bounded query and these optional scope constraints, here are the relevant tools* — regardless of what happens before or after the call. Recognizing whether a request is multi-scope or compound, and splitting it accordingly, is the calling layer's responsibility.

In practice, this leaves the calling layer (the LLM, or an orchestrator sitting in front of it) with two patterns, and most real workloads will use both, depending on the query:

- **Upfront fan-out.** When sub-queries are independent of each other's results — true of both the sales/legal multi-scope example and the engineering/revenue compound example above — the client can identify the relevant namespaces immediately, fire an `axiolex_discover_tools` call scoped to each (or one call with multiple namespaces, for the multi-scope case — see Section 9), and build a full execution plan before calling anything. This is cheaper in round-trips and easier to reason about as a static plan.
- **Discover → execute → discover.** When a later sub-query depends on data only available after an earlier tool has run — for example, "find the business units with the worst forecast variance, then check whether we have headcount approval to hire in those units" — the second discovery call cannot be fully specified until the first tool's result is known. Here the client has to recognize the dependency and defer the second discovery call until the right point in its own execution loop. This pattern can apply to either a multi-scope or a compound request, depending on whether the later step's domain was already known upfront or only becomes clear from the earlier result.

Both patterns sit on top of the same stateless discovery contract without Axiolex needing to know or distinguish between them, which is what keeps the two concerns — retrieval quality and orchestration strategy — from leaking into each other.

## 8. Why relying on MCP's `list_changed` notification is not sufficient on its own

The Model Context Protocol defines a mechanism for servers to signal that their tool catalog has changed: a server with the `listChanged` capability can send `notifications/tools/list_changed`, and a compliant client is expected to react by re-fetching the tool list — in principle, without requiring a full reconnect. This is a real, useful mechanism, and it is worth being precise about exactly what it does and does not cover.

**What `list_changed` can address, when implemented and honored.** For a server the client is already connected to, a tool being added, removed, or modified on that server can in principle be communicated without a full session reconnect — this is the scenario the notification exists to solve, and where it works, it works as designed.

**What `list_changed` cannot address, by definition.** A newly deployed MCP server that the client has never been configured to connect to is invisible regardless of whether that new server implements `listChanged` correctly, because the client was never connected to it in the first place to receive any notification from it. Server discovery — learning that a new capability provider exists at all — is a different problem from tool-list synchronization on a connection that already exists, and no version of the notification mechanism addresses the former.

Even within its intended scope, coverage is not guaranteed, for concrete reasons:

- **Client-side support is inconsistent.** Not every MCP client implementation listens for and acts on this notification the same way. Some perform a full session re-initialization on receipt, some only pick up changes on the next new session, and some do not implement the handler at all.
- **It's server-initiated, and many servers don't implement it.** The mechanism only helps if the MCP server actually sends the notification when its catalog changes. Many internal or homegrown MCP servers — exactly the kind an enterprise is likely to have many of — do not implement `listChanged` at all, in which case the client has no visibility into the change regardless of its own capability.
- **In-flight conversations can still act on stale tool shapes.** Even where the notification fires and the client dutifully re-fetches, a conversation already in progress may have context (a prior tool description, a parameter name referenced earlier) that doesn't automatically get corrected mid-conversation — the refreshed list needs to actually be re-consulted for the specific turn where it matters.

The practical consequence: new-server discovery still requires explicit client-level configuration no matter how well `list_changed` is implemented, and tool changes on an existing connection depend on both the server and the client correctly implementing and honoring the notification path — which is a narrower and more fragile guarantee than it may first appear.

This is the concrete argument for centralizing discovery through a system like Axiolex rather than relying on each MCP server's own change-notification behavior — and it holds even in the best case where every connected server implements `listChanged` correctly and every client honors it. Enterprise inventory (what capabilities exist across the company, who publishes them, where they are currently deployed) and new-capability discovery are simply outside what a per-connection notification mechanism was ever designed to solve. Axiolex's catalog reflects the current state on every call, by construction, because there's nothing to notify — the client asks fresh each time instead of holding a snapshot that needs to be invalidated, and a newly added provider is visible on the next call without any client needing to have been told it exists in advance.

## 9. Should the LLM infer the namespace itself?

`axiolex_discover_tools` can be called with an explicit namespace, multiple namespaces, or none (`all`). A natural question is whether the calling LLM can be trusted to determine the right namespace itself and pass it along, rather than requiring the calling application to specify it.

**The `namespace` parameter has one semantics, regardless of who supplies it or how many are passed: it is a hard search boundary, not a ranking preference.**

- A single namespace searches only that namespace.
- Multiple namespaces search the union of those namespaces, still excluding everything else.
- Omitting the parameter, or passing `all`, searches the full catalog.

There is no intermediate behavior where a stated namespace is treated as a soft preference and Axiolex quietly searches outside it anyway. This is the same hard-boundary guarantee described in Section 6 for an application-constrained call (`namespace="hr.recruiting"` from an HR recruiting application) — and it holds identically whether the namespace was supplied by an application's own code or by an LLM's inference. Axiolex does not distinguish between the two by softening one case and not the other; the contract for the parameter is the same regardless of caller.

This matters because it keeps the contract deterministic and debuggable. If `axiolex_discover_tools` sometimes respected a stated namespace exactly and sometimes silently expanded past it depending on internal confidence scoring, a caller receiving zero results, or a caller receiving unexpected out-of-namespace results, would have no reliable way to know which behavior it got without additional instrumentation. A single, fixed semantics for the parameter — supplied means bounded, always — removes that ambiguity entirely.

**Confidence and ambiguity handling belongs to the caller, not to Axiolex.** Only the caller — the LLM or the application constructing the call — has visibility into how confident it actually is about the domain of a given query. Axiolex has no way to distinguish "the caller is highly confident this is Legal" from "the caller is guessing," so it should not attempt to compensate for low confidence by loosening a boundary it was explicitly given. Instead:

- If a query maps clearly to one domain, the caller passes that single namespace, and gets a hard-bounded result.
- If a query is genuinely ambiguous about which single domain it belongs to — "check contract status for the deal," which could mean Sales or Legal depending on what "status" refers to — the caller should pass both candidate namespaces: `namespaces=["legal", "sales"]`. This is a distinct case from the multi-scope and compound requests discussed in Section 7: there, the request's domain requirements are known and the query genuinely needs multiple namespaces; here, the request likely belongs to exactly one namespace, but the caller doesn't know which, and passing both is a way of hedging that uncertainty rather than a claim that both are actually needed.
- If a query's domain can't be determined at all, the caller omits the namespace or passes `all`, accepting a full-catalog search rather than guessing at a single namespace and being wrong.

`axiolex_list_namespaces` still does real work here — exposing namespace names alongside short, disambiguation-focused descriptions (see the `hr.recruiting` vs. `hr.employee_services` case) reduces how often a caller ends up in the genuinely-ambiguous case to begin with, by grounding namespace selection in served data rather than the model's own guesswork. But its job is to make the caller's *choice* better before the call is made, not to give Axiolex license to override that choice after the call arrives.

This distinction matters most where it intersects with authorization. A hard-bounded namespace parameter is what makes namespace-based access control meaningful in the first place: if `axiolex_discover_tools` could silently search outside a stated namespace under any circumstance, a namespace restriction tied to a user's permissions (Section 5) would not be a reliable boundary. Enforcing `namespace` as a hard filter for every caller, not just application-constrained ones, is a precondition for authorization scoping to actually hold — not a separate concern layered on top of it.

## 10. Evaluating discovery quality

Because tool retrieval is a search problem, it can be evaluated like one: query sets with known-correct tool matches, run against the retrieval configuration, scored for precision and recall at the top of the ranking.

Axiolex supports tuning this retrieval — lexical matching (BM25), dense semantic matching (ColBERT), weighted combination of the two, and reciprocal rank fusion (RRF) across methods — and an evaluation platform that runs these configurations against a corpus of past queries with known-correct tool sets. Two things are worth measuring as distinct metrics, because they fail independently:

- **Tool retrieval accuracy**: given a query (and optionally a namespace), does the correct tool set actually appear at the top of the ranking?
- **Namespace selection accuracy**: when the calling LLM chooses the namespace (rather than an application hardcoding it, as in the HR recruiting case), does its chosen namespace match the correct one — measured separately from whether the right tool was ultimately found, since a wrong namespace with a lucky retrieval and a right namespace with poor retrieval are different failures requiring different fixes.

Logging actual query → namespace → tool selections in production and feeding them back into this evaluation set is what turns namespace and description tuning from a one-time design exercise into an ongoing, measurable process — the same discipline applied to tool descriptions extends naturally to namespace descriptions and decomposition quality.

## 11. Summary of boundaries

| Layer | Responsibility | Owner |
|---|---|---|
| Request analysis | Recognize whether a request is multi-scope (one intent, multiple domains), compound (multiple independent intents), or domain-ambiguous (one intent, unclear domain), and query accordingly | Calling LLM / orchestrator |
| Discovery | Given a bounded query and optional namespace/scope, return relevant tools, schemas, and endpoints | Axiolex |
| Namespace selection | Choose which namespace(s) to pass — single, multiple, or `all` — based on confidence in the query's domain | Calling LLM / orchestrator (Axiolex enforces whatever is passed as a hard boundary) |
| Execution sequencing | Decide upfront fan-out vs. discover→execute→discover based on data dependencies | Calling LLM / orchestrator |
| Execution | Resolve a discovered tool's endpoint and invoke it | Axiolex (`axiolex_execute_tool`) — required for fixed-integration clients (Claude, Cursor); optional convenience for developer-built applications, which may call the resolved endpoint directly |
| Authorization | Restrict what a given user or client can discover or execute | Axiolex, enforced from authenticated identity, not from inferred namespace |
| Catalog currency | Reflect current tool state (additions, renames, retirements) without requiring client reconnection | Axiolex |

Axiolex's own responsibility, within this, stays deliberately narrow: resolve a bounded query and a scope into a relevant, current set of capabilities, and provide a stable execution path for clients that can't dynamically register new tools mid-session. Everything above that — how a query gets broken down, when to call discovery relative to execution, how confident to be in an inferred namespace — is left to the calling layer, which is what allows very different clients (a fixed-integration agent like Claude or Cursor, an MCP-native internal application, or a REST-based caller) to sit on top of the same discovery contract without Axiolex needing to know or accommodate the differences between them.
