# Security Policy

## Project Status

**Streaming System + Compass** is an active research and reference implementation. The repository does not currently define stable supported release lines or a production security-support commitment.

When reporting a finding, identify the affected commit or repository state rather than assuming a supported released version.

## Security-Sensitive Findings

Credible security-sensitive findings may include implemented behavior that permits:

* bypassing accepted-history mutation protections;
* escaping an authorization or database permission boundary;
* bypassing semantic admission for a state-changing operation;
* failing open where a state-changing operation should stop;
* exposing credentials, secrets, or sensitive evidence;
* targeting a non-test database through destructive test infrastructure;
* escalating agent or workflow authority through implemented repository behavior.

Future architecture ideas, explicitly deferred capabilities, and unimplemented governance responsibilities are not automatically vulnerabilities. A report should identify an implemented behavior, executable path, or concrete repository artifact that creates the security impact.

## Reporting a Vulnerability

Do not publish exploit details, credentials, sensitive evidence, or a working exploit in an ordinary public issue.

Repository-visible metadata does not currently establish that GitHub Private Vulnerability Reporting is enabled. The maintainer intends to use GitHub Private Vulnerability Reporting as the preferred private route once it is enabled.

If the repository's GitHub **Security** page offers a private **Report a vulnerability** action, use that route. Until a private route is available, use a minimal, non-sensitive request through the public project or maintainer channels asking to arrange private coordination. Do not identify the vulnerable component, reproduction steps, secret values, or exploit details in that public request.

## What to Include Privately

Once a private channel is established, include the information needed to understand the boundary and reproduce the issue safely:

* affected commit or repository state;
* affected component or boundary;
* reproduction conditions;
* expected and observed behavior;
* security impact;
* whether accepted authority, permissions, or semantic admission can be bypassed;
* whether destructive or state-changing behavior is involved;
* minimal reproduction details that do not expose unrelated sensitive data.

A publicly posted proof of concept is not required.

## Coordinated Disclosure

Please avoid public disclosure of exploitable details until the maintainer has had a reasonable opportunity to investigate and coordinate a response. This policy does not promise a fixed acknowledgement, remediation, or release timeline.

## Scope Boundary

This repository explores correctness, admission, evidence, permission, and authority boundaries. It is not currently presented as a production security product.

The existence of this policy does not imply that every future Compass decision, strategy, retry/attempt-authorization, or action-safety capability is already implemented or security-supported.
