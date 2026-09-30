# Security

Axiolex is an MCP gateway. Protecting its inbound endpoint is important because
it may provide access to multiple downstream MCP providers.

## Inbound authentication modes

| Mode | Intended use | Do not use for |
| --- | --- | --- |
| `OFF` | Local development on loopback only | A LAN, shared host, or production environment |
| `STATIC_SHARED_TOKEN` | A controlled development LAN, demonstration, CI, or service-to-service connection | Distributing access to individual employees |
| `EXTERNAL_TOKEN` | Enterprise deployment behind an identity-aware gateway | Direct public exposure without a gateway |

`STATIC_SHARED_TOKEN` requires every client to send the same bearer token. It
is deliberately simple, but it does not identify individual users, cannot
revoke one user's access without rotating the token for every client, and must
not be sent over unencrypted HTTP outside an isolated development network.

## Enterprise employee access

Do not give employees the Axiolex static shared token or ask them to paste it
into Claude, Codex, or another MCP client's local configuration.

Instead, expose one canonical HTTPS endpoint through a company-managed,
identity-aware reverse proxy or API gateway:

```text
Employee MCP client -- company SSO --> gateway --> Axiolex --> MCP providers
```

The gateway should:

- authenticate employees with the organization's identity provider (for
  example, OIDC through Entra ID, Okta, or Google Workspace);
- enforce authorization policy and record an audit trail per user;
- issue or forward short-lived, audience-restricted access tokens, or inject a
  gateway-to-Axiolex credential after authenticating the employee;
- remove client-supplied identity and authorization headers before adding
  headers it trusts; and
- be the only network path to Axiolex. Block direct employee and public access
  to the Axiolex application port.

With gateway token injection, an employee's MCP configuration contains only
the canonical endpoint, such as:

```text
https://axiolex.company.internal/mcp
```

It contains no long-lived Axiolex secret. The gateway holds its internal
credential in the organization's secret-management system and rotates it under
the organization's operational controls.

## Development LAN example

For a personal development LAN, an operator may use an internal name such as
`http://axiolex:9700/mcp` with `STATIC_SHARED_TOKEN`. Configure the same name
through internal DNS or each machine's `/etc/hosts` file. This is a development
convenience, not an enterprise deployment pattern; bearer tokens sent over
plain HTTP can be intercepted by a network observer.

## Token handling

Treat all bearer tokens as secrets:

- Never commit them to Git, include them in URLs, or log them.
- Store service credentials in a secret manager for managed deployments.
- Rotate a token immediately if it may have been exposed.
- Use HTTPS for any connection that leaves a tightly controlled local
  development environment.
