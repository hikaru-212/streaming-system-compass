# Action Path Admission

[← Back to Semantic Admission Index](README.md)

## The Drop-and-Recreate Trap

A candidate action is not an accepted fact.

The following failure case shows why final-state validation is not enough.

## User Intent

The user intent is straightforward:

> Modify `TableA.amount` from `INT` to `DECIMAL`.

A safe action path would be:

1. `ALTER_COLUMN TableA.amount TO DECIMAL`

But an agent could produce a very different path:

1. `DROP_TABLE TableA`
2. `CREATE_TABLE TableA(id INT, amount DECIMAL)`

## The Final State Looks Correct

Now look only at the final result:

```text
TableA.amount == DECIMAL
```

A naive final-state validator may say:

```text
PASS
```

The schema looks correct.

But the historical records are gone.

The workflow succeeded. The final state looks right. The system is still wrong.

This is the Drop-and-Recreate Trap.

The user asked for a type change.

The system got a table recreation.

The final state may satisfy the surface-level requirement while silently violating a deeper one:

> Preserve the existing data.

## Final State Is Not Enough

A correct-looking result does not prove that the action path was safe.

A successful workflow does not prove that the system preserved the right truth.

For enterprise agents, the deeper question is not only:

> Did the agent reach the requested end state?

It is also:

> What path did the agent take to get there?

And:

> Was that path admissible?

## Compass-Style Defense

A Compass-style guard checks a candidate action before it is executed.

For this intent:

```text
MODIFY_TABLE_A_COLUMN
```

The policy may say:

Allowed:

- `ALTER_COLUMN`

Blocked:

- `DROP_TABLE`
- `CREATE_TABLE`
- `TRUNCATE_TABLE`

So when the agent proposes:

```text
DROP_TABLE TableA
```

the system blocks it before it mutates state.

## Core Principle

Do not wait until the final state looks wrong.

Validate whether the action path is allowed before the system commits it.

A final-state validator asks:

> Did the result look correct?

A Compass-style admission guard asks:

> Was this action allowed to happen in the first place?

Some actions are technically executable but semantically unsafe.

That is why action path admission matters.
