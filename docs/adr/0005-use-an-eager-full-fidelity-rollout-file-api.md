---
status: superseded by 0027
---

# Use an eager full-fidelity rollout file API

`rollout-go` initially exposes one eager `Read(path) (File, error)` operation.
Each record retains its complete raw JSON, source line number, optional common
envelope, and optional line-local decode error. Malformed rows remain available
as evidence; only file I/O prevents the read from succeeding. Commands process
multiple rollout files one at a time. No streaming, iterator, visitor, registry,
or generic decoding abstraction is added until measured rollout sizes prove the
simple single-file API insufficient.
