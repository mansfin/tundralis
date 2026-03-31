# Tundralis Production-Readiness Checklist

Updated: 2026-03-30

This is the concrete hardening list for taking the current Tundralis KDA web app from strong internal/pilot tool to production-ready customer app.

## Current judgment

- **Internal MVP:** yes
- **Controlled pilot:** close
- **Production-ready for unattended customer use:** not yet

The main gap is not model capability.
The main gap is productization:
- reduce cognitive load
- remove operator/developer residue
- make the results feel premium
- add browser-level regression guardrails

---

## Tier 1 — do next

### 1. Simplify the default mapping experience

**Goal**
Make the setup page feel 40% lighter without removing power.

**Current problems**
- Mapping page tries to be recommendation explainer, config console, transform studio, segment builder, and field debugger at the same time.
- Too much is visible by default.
- The predictor area becomes a checkbox wall.
- The page reads like a power-user workbench, not an opinionated SaaS flow.

**Must-change behaviors**
- Default first view should be: recommended outcome, recommended drivers, run readiness.
- Advanced details should be collapsed by default.
- Excluded/helper/ambiguity details should not dominate the main fold.
- Recode and segment work should feel optional, not co-equal with the main path.

**Acceptance criteria**
- A first-time user can understand the default recommended setup in under 15 seconds.
- A first-time user can run a clean file without ever opening advanced sections.
- The page above the fold communicates outcome, drivers, confidence, and next action clearly.

---

### 2. Remove debug and operator residue

**Current problems found in repo**
- `#mappingDebug` is still rendered in `web/templates/mapping.html`
- mapping page contains obvious initialization/debug plumbing leaking into the user surface
- some copy still sounds like internal analyst or heuristic language rather than product language

**Actions**
- Remove `mappingDebug` from normal UI entirely
- If needed, gate debug output behind explicit dev flag only
- Audit visible labels/copy for dev-facing language
- Remove any residual temporary placeholders or scaffold-y UI states

**Acceptance criteria**
- No user-visible debug text in standard mode
- No internal terminology visible unless deliberately exposed in an advanced/details context

---

### 3. Upgrade the results page into an insight page

**Current problems found in repo**
The current `web/templates/result.html` is functional but too thin:
- small stats row
- top priorities list
- optional segment summaries
- preview image gallery
- download links

It currently feels like a finished batch job, not a finished product moment.

**Actions**
- Add an executive summary hero
- Surface top 3 recommended actions more clearly
- Better frame model quality/confidence
- Make segment insight more legible
- Make artifact download feel like the end of a premium flow, not raw file access

**Acceptance criteria**
- A user can understand the main answer without opening the deck
- The page communicates what happened, what matters, and what to do next
- Downloads feel secondary to insight, not the only output

---

### 4. Do a full UX pass on segments + recodes

**Current problems found in repo**
- Recode flow is powerful but interaction-heavy
- Segment builder currently exposes both simple and nested logic in one surface
- Nested tree is likely too prominent for MVP behavior
- Save/draft/refresh mental model is still heavier than it should be

**Actions**
- Make simple segment creation the primary path
- Move nested tree into advanced mode
- Tighten wording around save/update/refresh
- Improve empty states and validation states
- Clarify when preview data is stale vs refreshed

**Acceptance criteria**
- Simple segment creation works with almost no explanation
- Nested tree exists, but only for advanced cases
- Users can tell whether saved segments/adjustments are already applied

---

### 5. Add browser-level regression checks for the real user flows

**Why**
You already got bitten by browser/hydration behavior. Unit tests won’t catch that class of failure.

**Minimum required coverage**
- Upload page loads
- upload POST returns redirect / completes successfully
- mapping page hydrates
- outcome control populates
- predictor list renders
- workflow tabs switch
- result page renders downloads and preview content

**Recommended execution modes**
- local deterministic browser test against app environment
- lightweight smoke against live app when safe

**Acceptance criteria**
- A broken mapping-page hydrate is caught before release
- A broken results-page render is caught before release

---

## Tier 2 — immediately after Tier 1

### 6. Tighten copy system-wide

**Direction**
- concise by default
- details on demand
- less implementation vocabulary
- more decisive product language

**Replace this style**
- heuristic-heavy explanations
- analyst-tool vocabulary
- long always-visible explanation blocks

**With this style**
- Recommended outcome
- Recommended drivers
- Ready to run
- Review this if something looks wrong
- Add segments if you want breakouts

---

### 7. Rework predictor selection UX

**Current problem**
The candidate driver picker is functional but visually heavy.

**Upgrade direction**
- Recommended vs additional vs excluded grouping
- Show top shortlist first
- Expand to show all
- Visually separate selected state from available state more strongly
- Consider grouping by battery/family when available

---

### 8. Improve file context and dataset summary

**Current problem**
Real upload filenames are ugly and visually noisy.

**Upgrade direction**
- shorten display filename by default
- reveal full filename on demand
- add a compact file summary card:
  - rows
  - columns
  - numeric fields
  - possible segment fields
  - schema confidence

---

### 9. Deliberate responsive sanity pass

Desktop-first is fine.
Broken-on-narrow screens is not.

**Need**
- mapping page remains usable on laptop/narrow desktop
- inspector doesn’t become a punishment box
- workflow tabs don’t become unreadable
- results page stacks cleanly

---

### 10. Improve long-running state UX

**Need better status handling for**
- upload completion → mapping prep
- preview refresh
- run-analysis
- artifact generation

**Acceptance criteria**
- user always knows whether work is happening
- user always knows whether inputs are stale
- failure states include recovery guidance

---

## Tier 3 — strategic polish

### 11. Standardize confidence / review messaging

Need a cleaner confidence language system:
- high confidence
- review recommended
- needs clarification

This exists partially now, but should become more consistent and easier to scan.

### 12. Improve customer handoff moment

Final product feeling should be:
- here’s the answer
- here’s the story
- here’s the deck
- here’s what to do next

Not:
- here are some files

---

## Suggested 2-week execution order

### Week 1
1. Simplify mapping default UX
2. Remove debug/operator residue
3. Tighten copy
4. Rework recode + segment interaction design
5. Add browser regression smoke coverage

### Week 2
6. Redesign results page into insight page
7. Run 3 ugly real datasets end-to-end
8. Fix friction uncovered by those runs
9. Polish artifact/download experience
10. Freeze MVP vs advanced scope

---

## Definition of production-ready for this app

Tundralis is production-ready when:
- a new user can upload a reasonable file and reach a correct run without hand-holding
- the mapping page feels guided rather than overwhelming
- the results page communicates insight, not just completion
- no debug/operator residue leaks into the product
- core browser flows are covered by regression tests
- ugly real survey exports do not make the UI feel fragile

---

## Single strongest recommendation

If only one thing gets done next:

**Make the mapping page feel much lighter by default without removing any power features.**

That is the highest-leverage production-readiness move because the engine is already ahead of the UX.
