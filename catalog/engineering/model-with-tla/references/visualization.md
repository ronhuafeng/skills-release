# Model visualization

Model visualization has several representations. Each answers a different
question and carries a different evidence strength.

## Semantic statechart

A manually curated statechart explains intended product behavior. Nodes
represent domain phases. Edges name actions and important guards. Identity,
observation quality, ownership, and policy usually remain orthogonal annotations
instead of becoming a node for every variable combination.

The statechart is a communication artifact synchronized with the requirements
model. It is not an exhaustive reachable-state graph.

## Reachable-state graph

A TLC DOT dump visualizes the states reached by one finite configuration. The
relevant TLC option is:

```text
-dump dot,colorize,actionlabels /absolute/temp/model.dot
```

The output belongs outside the repository and can be rendered with GraphViz.
Large verification configurations often produce unreadable graphs. A smaller
visualization configuration is exploratory and does not replace the
verification configuration or justify a narrower completion claim.

## Counterexample trace

A state sequence or sequence diagram explains one property failure. Useful
fields include initial authority and ownership, action order, changed variables,
late or failed results, the violation, and the corrected commit or cleanup gate.

The bundled TLC prints a counterexample to standard output; `-difftrace` limits
that output to variables changed between adjacent states. TLA+ Toolbox Trace
Explorer can evaluate expressions across trace states when available. The
bundled TLC version does not provide a separate `-dumpTrace` option.

## Action graph

An action graph summarizes which actions followed one another during a
simulation. It represents sampled relationships, not exhaustive state-space
proof.

## Representation map

| Question | Representation |
|---|---|
| What is the intended lifecycle? | Semantic statechart |
| Which states did a small finite config reach? | TLC DOT state graph |
| How did a property fail? | Counterexample trace or sequence diagram |
| Which action combinations appeared in simulation? | Action graph |
