# Compass (Invariant Engine)

This module defines and enforces system invariants.

## Responsibilities

- Validate state transitions
- Detect semantic violations
- Enforce system correctness at runtime

## Core Idea

Invariant = State Compression + Contract

## Validation Logic (Example)

Example of a semantic violation:

- If current_state == SHIPPED and event == PAYMENT_ADJUSTED  
  → This is a semantic breach

- If paid_amount != total_amount when state ∈ {PAID, SHIPPED}  
  → Invariant violation

## Future Work

- Policy-driven validation
- Dynamic rule injection
- Failure classification