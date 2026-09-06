# Concurrency contracts

A concurrent model must state which histories are acceptable. A correct final
state cannot establish that overlapping operations observed a valid history.

## Operation history

When operations can overlap, preserve the distinctions needed by the target
contract:

- operation identity and target incarnation;
- invocation and response events;
- pending, completed, failed, or unknown outcome;
- returned result and externally visible effect;
- client order and relevant real-time precedence.

Do not add a complete event log when the property needs only a smaller history
projection. Do not omit invocation or response boundaries when the property
depends on them.

## Select the consistency contract

Choose the governing contract. Do not select the strongest familiar name by
default.

- **Linearizability:** each completed operation takes effect at one point
  between invocation and response, and the order preserves real-time
  precedence.
- **Sequential consistency:** one total order preserves each participant's
  program order but need not preserve real-time precedence between participants.
- **Serializability:** concurrent transactions are equivalent to a serial
  order. Use strict serializability when real-time precedence is also required.
- **Snapshot isolation:** transactions read from snapshots and follow its write
  conflict rules. It is not equivalent to serializability.
- **Causal or eventual consistency:** define the causal-order or convergence
  obligation and the conditions under which it must hold.

Final-state equality, raw response equality, and per-operation success are not
substitutes for the selected history property.

## Environment and fault envelope

Record each relevant interference or fault with:

| Field | Question |
|---|---|
| Allowed behavior | Can work be lost, duplicated, reordered, delayed, or partitioned? |
| Observation | How does the system distinguish failure, absence, and unknown? |
| Persistence | Which state survives a crash or restart? |
| Recovery and ownership | Who retains responsibility, and what confirms convergence? |
| Progress assumption | Which environment event or scheduling condition is required? |

Model only faults that can change a checked property or its assumptions. State
important exclusions explicitly.

## Memory, time, and progress

For shared-memory algorithms, name the memory model or declare it outside the
claim. Do not assume sequential consistency when the implementation relies on a
weaker memory model.

Separate logical order from real-time guarantees. A finite clock abstraction
can check ordering and bounded-domain properties, but timestamp observations do
not establish an unmodeled timing guarantee.

Distinguish intended termination, quiescence, and deadlock. Select only the
progress contract required by the system, such as deadlock freedom, starvation
freedom, system-wide lock freedom, per-operation wait freedom, or a named
domain-specific convergence property.

For an open system, state environment assumptions separately from the system
guarantee. Fairness does not replace an environment contract that supplies the
event needed to enable progress.
