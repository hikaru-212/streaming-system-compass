# Indirect Authority Escalation Demo

## Status

```text
branch
= experiment/indirect-authority-escalation-demo

current delivery
= PR1 — threat model and semantic authority boundary

implementation
= not started
```

This document defines the boundary for a future deterministic local experiment.
PR1 is documentation-only. It adds no runtime behavior, tests, production
Compass policy, or external integration.

The experiment is informed by the repository's existing distinction between
candidate actions and accepted facts, especially the public concept note
[Shared Workflow Is Not Shared Authority](../../docs/semantic_admission/shared_workflow_is_not_shared_authority.md),
the current [Durable History Permission Boundary](../../docs/boundary_notes/durable_history_permission_boundary.md),
and the completed [Stage 4B.5 boundary](../../docs/implementation_notes/stage_4b_5/README.md).
Those sources do not claim that production Compass already implements the
inventory policy defined here.

---

## Research Question

The experiment will ask whether a directly denied authoritative effect can
remain reachable through a composition of individually allowed operations:

```text
direct permission denied
!=
authoritative effect unreachable
```

The target failure shape is:

```text
LIMITED_AGENT
→ allowed RestockWorkflow
→ allowed InventoryAuthorityService
→ authoritative inventory effect
```

The core distinctions are:

```text
direct permission
!=
reachable authority

edge-valid
!=
path-authorized

tool permission
!=
effect authority

candidate produced
!=
fact established
```

The experiment must not reduce to an omitted local access-control check. Case 1
must prove that direct denial exists and works. Case 2 must then preserve every
required local permission while exposing a separate semantic promotion failure.

The broader intuition:

```text
reachable_effects(actor)
⊆
authorized_effects(actor)
```

is useful motivation, but it is not the executable V1 invariant. A limited
actor may legitimately initiate a workflow whose effect is later supported by
an independently authoritative source.

---

## Threat Model

| Element | V1 definition |
|---|---|
| Protected authoritative effect | Append an `AcceptedStockReplenished(product_id="product-a", quantity=10)` fact to accepted inventory history. |
| Limited actor | `LIMITED_AGENT` may read inventory and request replenishment, but may not append accepted replenishment facts or certify that stock was received. The actor need not be malicious. |
| Allowed workflow | `RestockWorkflow` may accept a restock request, construct a `CandidateStockReplenished`, preserve its lineage and evidence, and submit it to the privileged service. |
| Privileged component | `InventoryAuthorityService` owns the intended accepted-fact append capability. Its possession of that capability does not prove that every candidate it receives is supported. |
| Semantic boundary | `SemanticAuthorityAdmission` evaluates whether the exact candidate has evidence sufficient for promotion to `AcceptedStockReplenished`. |
| Failure condition | An accepted replenishment is appended using only workflow completion or agent-request-derived evidence, while the agent's direct append remains denied and every invoked local workflow edge remains allowed. |

### V1 assumptions

The future implementation is intentionally bounded to:

```text
single process
deterministic
in memory
standard library only
no LLM
no network
no external service
no credentials
no concurrency
no retry
no sandbox escape
no exploit behavior
```

V1 does not model hostile-process isolation, component impersonation,
cryptographic authenticity, PKI, IAM, or production identity wiring. It models
the authority-composition shape with explicit finite identities and operations.

---

## Demo-Local Actors and Components

| Name | Responsibility | Explicit non-authority |
|---|---|---|
| `LimitedAgent` | Initiates a restock request and may issue agent-request evidence. | Cannot assert physical receipt or append accepted inventory facts. |
| `RestockWorkflow` | Converts the request into a candidate and transports lineage and evidence. | Cannot manufacture warehouse confirmation, approve promotion, or append accepted facts. |
| `InventoryAuthorityService` | Owns the privileged append path and, in the governed case, requests a promotion decision. | Local append capability is not evidence that a particular candidate is true. |
| `SemanticAuthorityAdmission` | Evaluates exact candidate correlation, proposition support, evidence-source authority, and modeled issuance. | Does not become generic RBAC, IAM, a tool firewall, or a persistence/concurrency gate. |
| `AuthoritativeInventoryStore` | Stores accepted inventory facts and rejects callers without the local append capability. | Requests, candidates, and workflow success do not become authority merely by reaching the store boundary. |
| `WarehouseAuthority` | May issue modeled warehouse receipt confirmation after making its own authority-bearing assertion. | Being causally triggered by a request does not force it to derive its assertion from that request. |
| `InventoryApprover` | May explicitly approve the exact replenishment candidate. | Approval is candidate-scoped and must not be inferred from workflow completion. |

These are demo-local responsibilities, not a production deployment topology.

---

## Authoritative State

Authoritative state is accepted inventory fact history:

```text
accepted_facts = (
    AcceptedStockReplenished(...),
    ...
)
```

For V1, current inventory is a deterministic fold over that history:

```text
inventory(product_id)
= sum(quantity for matching AcceptedStockReplenished facts)
```

The protected mutation is therefore the append of an accepted replenishment
fact. The visible inventory increase is the deterministic consequence of that
append.

The following remain non-authoritative:

```text
RestockRequest
CandidateStockReplenished
workflow success
candidate identity
agent request evidence
```

`RestockRequest` means that replenishment was requested.
`CandidateStockReplenished` means that replenishment is proposed.
`AcceptedStockReplenished` means that the system admitted replenishment as an
authoritative inventory fact.

Separate candidate and accepted conceptual types make this promotion visible.
A candidate identifier may exist before promotion, but identifier existence does
not establish accepted-history membership.

---

## Capability Graph

The capability graph answers only:

```text
Which component may invoke which local operation?
```

It does not answer whether evidence is authoritative for a business
proposition.

```text
LIMITED_AGENT
    ── SUBMIT_RESTOCK_REQUEST / ALLOWED ──► RestockWorkflow

RestockWorkflow
    ── SUBMIT_REPLENISHMENT_CANDIDATE / ALLOWED
    ──► InventoryAuthorityService

InventoryAuthorityService
    ── APPEND_ACCEPTED_REPLENISHMENT / ALLOWED
    ──► AuthoritativeInventoryStore

LIMITED_AGENT
    ── APPEND_ACCEPTED_REPLENISHMENT / DENIED
    ──► AuthoritativeInventoryStore
```

Case 3 adds this semantic decision path:

```text
InventoryAuthorityService
    ── REQUEST_AUTHORITY_PROMOTION_DECISION / ALLOWED
    ──► SemanticAuthorityAdmission
```

The existing workflow permissions remain unchanged. Case 3 introduces an
additional semantic promotion requirement before the privileged append
capability may be exercised. It does not make the complete Case 2 and Case 3
topologies literally identical.

---

## Evidence-Authority Graph

The evidence-authority graph answers a different question:

```text
Which modeled source may assert which proposition?
```

```text
LIMITED_AGENT
    ── may assert ──► RESTOCK_REQUESTED

WAREHOUSE_AUTHORITY
    ── may assert through WAREHOUSE_RECEIPT_CONFIRMATION
    ──► STOCK_REPLENISHED for the matching product and quantity

INVENTORY_APPROVER
    ── may explicitly approve
    ──► the exact CandidateStockReplenished
```

These structures must remain separate:

```text
capability authority
!=
semantic evidence authority
```

An actor may be allowed to submit a request without being authoritative for
physical receipt. A service may be allowed to append accepted facts without
every input it receives being eligible for promotion.

---

## Finite Evidence Model

V1 should use a closed, typed vocabulary rather than generic metadata or
free-text interpretation.

### Evidence kinds and propositions

| Evidence kind | Modeled issuer | Proposition supported |
|---|---|---|
| `AGENT_RESTOCK_REQUEST` | `LIMITED_AGENT` | `RESTOCK_REQUESTED` only |
| `WAREHOUSE_RECEIPT_CONFIRMATION` | `WAREHOUSE_AUTHORITY` | `STOCK_REPLENISHED` for the exactly correlated product and quantity |
| `INVENTORY_AUTHORITY_APPROVAL` | `INVENTORY_APPROVER` | Explicit approval of the exactly correlated replenishment candidate |

Minimum correlation fields are:

```text
candidate_id
product_id
quantity
```

The evidence record will also require its finite `kind` and modeled `issuer`.
The mapping from evidence kind to supported proposition must be contract data,
not another caller-selected free-form field.

Two distinctions are mandatory:

```text
evidence exists
!=
evidence authorizes the proposition

evidence matches candidate
!=
evidence source is authoritative
```

For example, `AGENT_RESTOCK_REQUEST` may match the candidate's identifier,
product, and quantity exactly. That establishes correlation with the originating
request. It supports `RESTOCK_REQUESTED`; it does not support
`STOCK_REPLENISHED`.

A matching `WAREHOUSE_RECEIPT_CONFIRMATION` may support
`STOCK_REPLENISHED` because V1 models `WAREHOUSE_AUTHORITY` as having authority
to assert receipt of the matching stock. This is a modeled semantic authority
relationship, not proof of a real warehouse system.

---

## Evidence Issuance Boundary

Evidence kind and issuer must not be modeled as arbitrary caller-controlled
string or enum assignments. A caller must not be able to obtain authoritative
support merely by constructing:

```text
kind = WAREHOUSE_RECEIPT_CONFIRMATION
issuer = WAREHOUSE_AUTHORITY
```

The future V1 model should preserve source-owned issuance responsibilities:

```text
LimitedAgent
→ may issue AGENT_RESTOCK_REQUEST

WarehouseAuthority
→ may issue WAREHOUSE_RECEIPT_CONFIRMATION

InventoryApprover
→ may issue INVENTORY_AUTHORITY_APPROVAL
```

Workflow components may preserve and transport evidence. They must not silently
manufacture a stronger kind, replace its issuer, or upgrade the proposition it
supports.

This is a modeled in-process issuance boundary. It does not provide signatures,
credentials, hostile-process security, cryptographic provenance, PKI, or IAM.

---

## Causal Lineage and Authority Basis

Causal lineage records how a candidate and its evidence came to be processed.
It is necessary for reconstruction, but it is not itself the authority rule.

In particular:

```text
causally triggered by the originating request
!=
authority derived from the originating request
```

A restock request may trigger a warehouse check. The resulting warehouse
confirmation remains authority-bearing if the warehouse makes its assertion
from the receipt facts it is modeled to own. The warehouse can therefore appear
downstream in the causal chain without its authority being derived from the
agent's request.

By contrast, a workflow that merely relabels the agent request as warehouse
confirmation has not introduced an authority-bearing assertion. Its stronger
claim still derives solely from the request and workflow completion.

For V1, authority-independent support means that the right and basis for the
source's assertion do not derive solely from the originating agent request or
the fact that the workflow completed. It does not mean that the issuer must be
absent from the causal lineage.

---

## Semantic Promotion Invariant

The V1 invariant applies at promotion from candidate to accepted inventory
fact:

```text
For every CandidateStockReplenished promoted to AcceptedStockReplenished:

there must exist evidence issued through its modeled source boundary

AND

the evidence must match the exact candidate

AND

the evidence kind must support STOCK_REPLENISHED

AND

the evidence issuer must have modeled authority to assert STOCK_REPLENISHED.
```

A formal sketch is:

```text
∀ candidate:

    promoted(candidate)

    ⇒

    ∃ evidence ∈ evidence_for(candidate):

        issued_by_modeled_source(evidence)
        ∧
        matches(evidence, candidate)
        ∧
        supports(evidence.kind, STOCK_REPLENISHED)
        ∧
        source_authorized_for(
            evidence.issuer,
            STOCK_REPLENISHED
        )
```

For V1, `matches` means equality of at least:

```text
candidate_id
product_id
quantity
```

The invariant deliberately preserves:

```text
correlation
!=
authority

local permission
!=
semantic promotion authority
```

Local capability checks determine whether an operation may be invoked.
`SemanticAuthorityAdmission` determines whether the candidate's evidence is
sufficient to establish the stronger accepted proposition.

---

## Required Cases

Each case begins from a fresh store with:

```text
accepted facts = 0
inventory = 0
```

### Case 1 — Direct Denial

The limited agent directly attempts the protected accepted-fact append:

```text
LIMITED_AGENT
→ APPEND_ACCEPTED_REPLENISHMENT(product-a, 10)
→ AuthoritativeInventoryStore
```

Expected observation:

```text
direct append = DENIED
candidate produced = NO
accepted facts = 0
authoritative effect reached = NO
inventory = 0
```

This case proves that the ordinary local permission boundary exists and works.

### Case 2 — Locally Valid Authority Composition Failure

The same actor uses only permitted workflow operations:

```text
LIMITED_AGENT
→ RestockRequest(product-a, 10)
→ RestockWorkflow
→ CandidateStockReplenished(product-a, 10)
→ InventoryAuthorityService
→ AcceptedStockReplenished(product-a, 10)
→ AuthoritativeInventoryStore
```

The vulnerable authority service incorrectly treats workflow completion or
request-derived evidence as sufficient support for `STOCK_REPLENISHED`.

Every required local edge remains allowed:

```text
LIMITED_AGENT → RestockWorkflow
SUBMIT_RESTOCK_REQUEST = ALLOWED

RestockWorkflow → InventoryAuthorityService
SUBMIT_REPLENISHMENT_CANDIDATE = ALLOWED

InventoryAuthorityService → AuthoritativeInventoryStore
APPEND_ACCEPTED_REPLENISHMENT = ALLOWED
```

Expected observation:

```text
direct permission = DENIED
local workflow edges = ALLOWED
candidate produced = YES
independently authoritative evidence = NO
accepted fact appended = YES
accepted facts = 1
authoritative effect reached = YES
inventory = 10
invariant = VIOLATED
```

The failure is not an absent ACL check, forged caller, or denied edge that was
bypassed. It is the invalid promotion of a request-supported candidate into a
stronger authoritative proposition.

### Case 3 — Semantic Authority Promotion

The existing request and candidate-production permissions remain allowed:

```text
RestockRequest
→ CandidateStockReplenished
→ SemanticAuthorityAdmission
→ AuthorityPromotionDecision
→ AcceptedStockReplenished, only after ACCEPT
→ AuthoritativeInventoryStore
```

Case 3 introduces an additional semantic promotion requirement before the
privileged service may exercise its append capability. It does not revoke the
agent's request permission, the workflow's candidate-production permission, or
the authority service's ownership of accepted-fact mutation.

With only exactly correlated `AGENT_RESTOCK_REQUEST` evidence:

```text
candidate produced = YES
evidence matches candidate = YES
evidence supports RESTOCK_REQUESTED = YES
evidence supports STOCK_REPLENISHED = NO
promotion = REJECTED
accepted fact appended = NO
accepted facts = 0
authoritative effect reached = NO
inventory = 0
invariant = PRESERVED
```

The decision must not be implemented as:

```python
if origin_actor == LIMITED_AGENT:
    reject
```

The candidate is rejected because its available evidence does not authorize the
proposition being promoted, not because an agent originated the workflow.

---

## Required Positive Control

A separate fresh-store control uses:

```text
same LIMITED_AGENT origin
+
same allowed workflow
+
same CandidateStockReplenished
+
matching WAREHOUSE_RECEIPT_CONFIRMATION
→ promotion may be ACCEPTED
```

Expected observation, assuming all other V1 conditions are satisfied:

```text
candidate produced = YES
warehouse evidence matches candidate = YES
warehouse evidence supports STOCK_REPLENISHED = YES
evidence source is authorized for STOCK_REPLENISHED = YES
promotion = ACCEPTED
accepted facts = 1
inventory = 10
invariant = PRESERVED
```

This control proves that the governed model is evidence-based rather than a
blanket rejection of agent-originated workflows. The warehouse may have been
causally triggered by the original request; its modeled assertion is still
authority-bearing because its authority basis is the warehouse receipt fact,
not the request itself.

---

## Compass Intervention Boundary

The demo uses Compass as a semantic promotion/admission concept:

```text
RestockRequest
→ CandidateStockReplenished
→ SemanticAuthorityAdmission
→ AuthorityPromotionDecision
→ AcceptedStockReplenished
→ AuthoritativeInventoryStore
```

The intervention occurs after the workflow has produced a candidate and before
the privileged append. It protects the transition from proposed replenishment
to accepted inventory fact.

The demo does not present Compass as:

```text
generic RBAC
tool firewall
IAM system
network security layer
cryptographic evidence service
```

The names `SemanticAuthorityAdmission` and `AuthorityPromotionDecision` are
demo-local. The design intentionally avoids reusing production
`AdmissionResult`, whose current repository responsibility is persistence and
concurrency admission rather than this semantic authority-promotion decision.

---

## Reviewer-Visible Comparison

| Observation | Case 1: direct | Case 2: indirect | Case 3: governed | Positive control |
|---|---:|---:|---:|---:|
| Direct agent append | `DENIED` | `DENIED` | `DENIED` | `DENIED` |
| Existing workflow permissions | Not used | `ALLOWED` | `ALLOWED` | `ALLOWED` |
| Candidate produced | `NO` | `YES` | `YES` | `YES` |
| Evidence supports `STOCK_REPLENISHED` | N/A | `NO` | `NO` | `YES` |
| Promotion | Not reached | Vulnerable / unchecked | `REJECTED` | `ACCEPTED` |
| Accepted facts | `0` | `1` | `0` | `1` |
| Inventory | `0` | `10` | `0` | `10` |
| Invariant | `PRESERVED` | `VIOLATED` | `PRESERVED` | `PRESERVED` |

---

## What This Demo May Eventually Claim

After the implementation and executable tests exist, the demo may claim:

```text
A deterministic local model demonstrates an authority-composition failure
where a directly denied authoritative effect becomes reachable through
individually permitted workflow edges.
```

It may also claim:

```text
A semantic authority-promotion requirement rejects unsupported promotion
while still permitting the same agent-origin workflow when independently
authoritative evidence exists.
```

Those claims must remain bounded to the finite, deterministic model and the
paths exercised by its tests.

## What This Demo Must Not Claim

The demo must not claim:

```text
this reproduces OpenAI internal architecture
this reproduces Hugging Face internal architecture
a specific external incident used this mechanism
the experiment exploits an external service
modeled evidence is cryptographically authenticated
modeled evidence has real external provenance
production Compass already enforces this inventory rule
Compass universally prevents authority escalation
```

It also must not claim production-grade hostile-process security, complete
causal provenance, complete IAM, or exhaustive authority-escalation coverage.

---

## Planned PR Sequence

```text
PR1
Threat model and semantic authority boundary

PR2
Deterministic direct-denial and locally-valid authority-composition
counterexample

PR3
Compass-inspired semantic authority admission + positive control

PR4
Reviewer-facing deterministic demo + final technical note
```

PR1 remains documentation-only. PR2 must not be implemented as part of this
delivery.

---

## PR1 Completion Boundary

PR1 is complete when:

1. authoritative state and the protected effect are explicit;
2. the capability graph and evidence-authority graph remain separate;
3. all three required cases and the positive control are specified;
4. causal lineage is separated from authority basis;
5. evidence correlation, proposition support, source authority, and issuance are
   distinct checks;
6. the semantic promotion invariant is reviewable;
7. current production Compass is not represented as implementing this policy;
8. the external-system and security claim boundaries are explicit; and
9. no Python, test, dependency, database, or production-governance change is
   included.
