# Produce or Review a Semantic Diagram

## Goal

Produce, refine, or review a source-grounded semantic diagram whose structured
source and rendered states support the intended meaning and reading experience.
Use the renderer selected for the task. The renderer owns its format and design
system; this contract owns semantic composition, geometry quality, repair, and
completion evidence.

## Contract

The **structured source** is the renderer input or inspectable artifact, such as
SVG, HTML, JSON, or diagram code.

A **render case** is
`{source_identity, viewport, color_scheme, state_identity}`. It binds each
visual observation to one structured-source version and one displayed state.

A semantic diagram always has:

- **Semantic structure**: each semantic element has an identity, meaning,
  owner, and authoritative source. Each relationship records its meaning and
  direction when the authoritative source defines direction.
- **Owned geometry**: one geometry source owns container bounds, child
  placement, padding, alignment, ports, and incident routes.

Add **adaptive layout** for maintainable or responsive outcomes and for
interactive states whose content or dimensions change the layout. Adaptive
layout recomputes owned geometry from component data.

Run all states internally. Treat user-provided audience, emphasis, and visual
style as design inputs. Resolve layout and quality decisions inside the loop.

## Agentic loop

```text
mode = the route selected by SKILL.md
review_findings = []
verification_limits = []
state = UNDERSTAND

repeat until the current turn pauses or reaches a delivery state:
    UNDERSTAND:
        verification_limits = []
        sources = select the smallest relevant authoritative inputs from:
            request, documentation, code, schemas, and supplied evidence
        semantic_model = derive entities, meanings, ownership, relationships,
            directions, invariants, unresolved facts, and the primary story
        fact_map = map every required fact to its authoritative source and
            responsible semantic element
        apply SEMANTIC_GATE
        if a required fact is unresolved: state = WAIT_FOR_INPUT
        otherwise: state = COMPOSE

    WAIT_FOR_INPUT:
        request only the unresolved facts required to preserve diagram truth
        pause the current turn
        after the answer: state = UNDERSTAND

    COMPOSE:
        if mode is EDIT:
            define hierarchy, node kinds, containers, dimensions, visual stack,
                ports, routing lanes, and reading order
            visible_map = assign every required fact to one visible owner in
                the overview, a detail view, a subgraph, a legend, or a note
            label_map = assign each label to its visible owner and one semantic
                purpose: identity, required fact, relationship distinction, or
                navigation
            choose manual geometry for stable simple layouts
            choose a data-driven generator or layout engine for repeated,
                compound, responsive, maintainable, or layout-changing
                interactive geometry
            make one geometry source own bounds, placement, ports, and routes
            generate the structured source
            source_identity = bind the generated structured source
        if mode is REVIEW:
            source_identity = bind the existing structured source and artifact
                identity
            derive its hierarchy, geometry ownership, ports, routes, and
                supported states while the artifact remains unchanged
            visible_map = locate each required fact in its current visible
                owner and mark facts that are absent
            label_map = map each existing label to its visible owner and
                semantic purpose
        required_render_cases = select every render case required by VISUAL_GATE
            for source_identity
        state = VERIFY_CODE

    VERIFY_CODE:
        code_result = inspect the structured source directly against CODE_GATE
        use a supported parser or validator when available
        if adaptive layout applies:
            if a supported working-copy regeneration path is available:
                change one representative label, component, or parent dimension
                    in a working copy
                regeneration_result = regenerate the structured source and bind
                    its source identity, viewport, color scheme, and state identity
                code_result += inspect regeneration_result.structured_source
                    against the adaptive CODE_GATE criterion
                add the render case bound to regeneration_result to
                    required_render_cases
            otherwise:
                adaptive_code_evidence = unavailable
        if required base or adaptive code evidence is unavailable:
            add the missing evidence to verification_limits
        if code_result requires repair:
            state = REPAIR when mode is EDIT
            if mode is REVIEW:
                add code_result findings to review_findings
                state = RENDER
        otherwise: state = RENDER

    RENDER:
        available_render_cases = identify render cases with source-matched
            rendered evidence already supplied
        missing_render_cases = required_render_cases - available_render_cases
        if missing_render_cases is not empty and an available renderer can
            faithfully produce them:
            render each missing case and add each successful case to
                available_render_cases
            missing_render_cases = required_render_cases - available_render_cases
        collect a screenshot or equivalent static visual for each available
            render case
        if missing_render_cases is not empty:
            add the missing visual evidence to verification_limits
        if available_render_cases is not empty:
            state = VERIFY_VISUAL
        otherwise:
            state = LIMITED_DELIVERY

    VERIFY_VISUAL:
        inspect the rendered evidence against VISUAL_GATE
        if visual repair is required:
            state = REPAIR when mode is EDIT
            if mode is REVIEW:
                add visual findings to review_findings
                state = REVIEW_RESULT
        otherwise:
            state = LIMITED_DELIVERY when verification_limits is not empty
            state = DELIVER when verification_limits is empty

    REPAIR:
        identify the semantic or geometry owner of the highest-impact failure
        if the failure concerns labels or text:
            preserve fact_map and the intended typography hierarchy
            repair = the first applicable repair or smallest sufficient
                combination from:
                consolidate repeated wording at its primary visible owner
                rewrite necessary text concisely
                move supporting detail to its semantic owner or a drill-down
                reflow content or allocate more space
        otherwise:
            repair = the smallest supported repair for that owner
        if repair exists:
            apply repair while preserving required meaning and legibility
            state = UNDERSTAND
        otherwise:
            add the unresolved user-visible impact to verification_limits
            state = LIMITED_DELIVERY

    REVIEW_RESULT:
        retain each user-visible issue, its location, and minimum correction
        state = LIMITED_DELIVERY when verification_limits is not empty
        state = DELIVER when verification_limits is empty
```

For an optional unresolved fact, omit the unsupported relationship or direction.
Represent uncertainty only when that uncertainty is part of the requested
story. A required unresolved fact pauses at `WAIT_FOR_INPUT`.

## Gates

### SEMANTIC_GATE

- Every required fact has an authoritative source and one responsible semantic
  element in `fact_map`.
- One primary story and its required supporting facts are selected.
- Every unresolved fact is classified as required or optional.

### CODE_GATE

- Semantic identities and references resolve to their intended elements.
- Every required fact resolves from its `fact_map` entry through `visible_map`
  to its intended owner in the structured source.
- Every label resolves through `label_map` to one visible owner and semantic
  purpose. Repeated wording supports a distinct reading path or hierarchy level.
- A relationship label adds meaning beyond endpoint identities, port roles, and
  arrow direction.
- The overview has a bounded information hierarchy; necessary detail resolves
  to its selected detail view, subgraph, legend, or note.
- Parent components own child placement. Repeated peers share dimensions,
  padding, and alignment rules.
- Routes derive endpoints from owned ports. The visual stack places boundaries,
  edges, nodes, labels, and text in that order or a renderer-equivalent order.
- Typography uses the renderer or design system's readable token for each
  semantic role at the intended display size. Text bounds use actual rendered
  font metrics or a conservative fallback.
- A maintainability, responsiveness, or layout-changing interaction claim has a
  representative regeneration check whose descendants and incident routes
  adapt from the same semantic and geometry sources.

### VISUAL_GATE

- Elements remain in bounds at the intended display size.
- Boxes, labels, arrowheads, turns, and unrelated routes remain distinct.
- Peers align, anchors meet their intended ports, and arrows express semantic
  direction.
- The primary story is visually dominant, and the target audience can follow it
  directly from the diagram.
- At the intended delivery size, rendered typography remains legible and the
  intended hierarchy among titles, body text, secondary text, and relationship
  labels remains clear.
- A responsive claim has readable evidence at the narrowest and widest intended
  viewports and at one representative viewport for each intermediate supported
  layout.
- Every supported color scheme and behaviorally or visually distinct selectable
  state has readable evidence. Equivalent states share one representative.

## Completion and delivery

- `EDIT` reaches `DELIVER` after the final artifact passes every applicable
  gate, including adaptive-layout verification when applicable. Present the
  final artifact, a useful preview or link, and a concise natural-language
  summary of the improved meaning and reading experience.
- `REVIEW` keeps the existing artifact unchanged and reaches `DELIVER` after
  every available gate has been inspected. Return the user-visible issues and
  minimum corrections.
- `LIMITED_DELIVERY` presents the verified artifact scope and any review
  findings. Summarize the highest-impact consequence of all verification limits
  as one natural-language limitation.

Internal states and repair transcripts remain working evidence rather than
normal user-facing output.
