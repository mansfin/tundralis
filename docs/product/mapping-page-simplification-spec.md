# Tundralis Mapping Page Simplification Spec

Updated: 2026-03-30
Target file(s):
- `web/templates/mapping.html`
- `web/static/app.css`
- any supporting server/template payload shaping needed for the simplified default view

## Objective

Make the mapping page feel substantially lighter and more opinionated without removing any current power.

This is not a backend feature project.
This is a product-shape project.

The rule:
- **keep power available**
- **hide complexity until needed**

---

## Current diagnosis

The current page is structurally strong but overloaded.

It currently behaves like all of these at once:
- recommendation summary
- outcome selection surface
- predictor curation workbench
- label cleanup tool
- semantic clarification console
- recode builder
- segment builder
- nested logic editor
- field profiler
- final run checklist

This makes the page feel longer and heavier than the user’s actual job.

The user’s real job is usually just:
1. confirm outcome
2. spot-check drivers
3. optionally add a segment
4. run

---

## Product principle

The page should communicate:

> Here is the recommended setup. You only need to touch the weird parts.

Not:

> Here is the full internal brain of the app.

---

## Proposed information architecture

## 1. Above-the-fold summary should become the primary product moment

### New default first card
A compact “Recommended setup” hero card should own the first screen.

**Visible by default**
- recommended outcome
- number of recommended drivers
- number of excluded fields
- confidence state
- usable rows
- primary CTA: `Run recommended setup`
- secondary CTA: `Review setup`
- tertiary CTA: `Adjust data`

**Collapsed by default**
- full explanation text
- full alternative outcomes list
- full excluded/helper/ambiguity breakdown
- semantic override actions

### Specific changes
- Remove `mappingDebug` entirely from standard UI
- Replace the current broad explanation block with a tighter executive summary
- Convert “Why this setup” into collapsible details
- Show only one or two sentences by default

### Default copy direction
- `Recommended outcome`
- `Recommended drivers`
- `Ready to run`
- `Review if something looks off`

---

## 2. Drivers section should move from checkbox wall to shortlist-first

### Current issue
The current candidate driver list is technically capable but visually dense.

### Proposed behavior
#### Default state
Show:
- selected recommended drivers
- top 8–10 recommended driver candidates in the picker
- a `Show all candidate drivers` control

#### Additional states
- `Recommended`
- `Additional candidates`
- `Excluded from modeling`

Even if this is implemented with simple sections instead of a fancy component, it will feel much more intentional.

### UX changes
- Make selected drivers feel like the primary truth
- Make the picker feel like an override tool
- Visually reduce the prominence of the full candidate wall

### Acceptance criteria
- User can understand what will be modeled without reading the full picker list
- User can still access every candidate field when needed

---

## 3. Move “label cleanup” into a lightweight advanced utility

### Current issue
Recommended rename fields and codebook upload are useful, but they currently take up too much surface area in the main recommendation flow.

### Proposed behavior
Put this inside a collapsed section labeled:
- `Improve labels (optional)`

Inside it:
- upload codebook
- rename recommended fields
- semantic clarification if still needed

### Why
This is valuable, but not on the critical path for a clean file.

---

## 4. Make “Adjust data setup” explicitly advanced

### Current issue
The recode builder is powerful but currently presented as a near-peer to the main setup path.

### Proposed behavior
Rename or position it more explicitly as advanced:
- `Advanced data adjustments`
- subtitle: `Only use this if Tundralis interpreted a field incorrectly or you need a custom derived field.`

### UI changes
- Keep the workflow tab, but visually de-emphasize it
- Collapse the entire section unless user opens it
- Tighten terminology:
  - `Field to adjust`
  - `Adjustment type`
  - `New field name`
  - `Saved adjustments`

### Interaction changes
- Saved recodes should be compact summary cards by default
- Editing should be inline only after explicit click
- Status copy should clearly distinguish draft vs saved

---

## 5. Make segments simple-first, nested-second

### Current issue
Simple and nested segmentation are both exposed in one visual block.
That makes segmentation feel more complex than the average user needs.

### Proposed behavior
#### Default segment mode
Simple builder only:
- segment name
- one or more simple rules
- AND/OR toggle
- saved segment previews
- save segment

#### Advanced segment mode
Collapsed control:
- `Use nested conditions`
- opens the tree editor only when requested

### Why
Most MVP use cases will be simple cut logic.
Nested trees are real power, but should not share top billing.

### Acceptance criteria
- A first-time user can create a basic segment without encountering the nested tree UI
- Advanced users can still access nested logic without friction

---

## 6. Reduce visible schema complexity in the default view

### Current issue
Candidate segments, helper/admin fields, ambiguity notes, and schema hints are all useful, but too much of that reasoning is visible at once.

### Proposed behavior
Turn schema reasoning into a compact summary row:
- `Confidence: high / review / needs clarification`
- `Possible segment fields: 3`
- `Fields needing review: 2`
- `Details`

Then move the full lists into the expanded details panel.

### Important
Do not remove this logic.
Just stop making every user read it immediately.

---

## 7. Make the confirm step shorter and more decisive

### Current issue
The confirm step currently replays a lot of setup state, but doesn’t feel notably more confident than the main recommended card.

### Proposed behavior
The confirm step should be a compact pre-flight check.

**Show**
- file
- outcome
- driver count
- adjustment count
- segment count
- validation issues if any
- final CTA

**Hide or collapse**
- long lists of all drivers/adjustments/segments unless user expands them

### Copy direction
- `Ready to run`
- `Needs attention before run`
- `Run KDA`

---

## 8. Reframe the field inspector as support tooling, not co-primary content

### Current issue
The sticky inspector is useful and should stay.
But visually it competes with the primary workflow.

### Proposed behavior
- Keep it sticky on large screens
- Collapse it by default on narrower screens
- Strengthen the visual hierarchy so the main flow remains primary
- Consider starting it in an empty/helpful state like:
  - `Select a field to inspect`
  - `Use this to spot-check questions, codes, and values`

### Why
It should feel like a helpful sidekick, not a second app running beside the first one.

---

## Concrete implementation changes

## Template changes

### Remove
- visible `#mappingDebug` block from standard mode

### Collapse by default
- recommendation details panel
- label improvement section
- helper/admin/ambiguity deep lists
- nested segment tree UI
- long confirm lists

### Add / restructure
- recommendation hero with stronger CTA hierarchy
- top-driver shortlist section
- `show all` behavior for candidate driver list
- simple-vs-advanced segment split
- compact confidence/status summary row

---

## CSS direction

### Reduce density
- more spacing between major sections
- less simultaneous box treatment inside the recommendation surface
- stronger hierarchy between primary and secondary cards

### Improve action hierarchy
- one obvious primary button per section
- secondary links/buttons should look secondary

### Improve long-page fatigue
- better collapsed-state defaults
- reduce number of simultaneously visible bordered boxes
- use summary rows instead of full detail blocks where possible

---

## Suggested implementation sequence

### Phase 1 — low-risk shape fixes
1. remove `mappingDebug`
2. collapse recommendation details by default
3. collapse label improvement section by default
4. hide nested segment tree behind advanced toggle
5. shorten confirm step

### Phase 2 — bigger UX wins
6. introduce driver shortlist + show-all pattern
7. simplify schema/confidence summary into a compact strip
8. tighten action copy and section subtitles
9. improve saved adjustment / saved segment card density

### Phase 3 — refinement
10. responsive pass for narrower screens
11. refine inspector hierarchy and collapsed behavior
12. test with ugly real datasets

---

## Definition of done

This spec is done when:
- the default mapping experience feels guided rather than exhaustive
- a clean-file user can run without touching advanced sections
- the page is materially shorter and lighter at first glance
- advanced features still exist, but only when needed
- no debug residue remains
