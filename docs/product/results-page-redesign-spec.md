# Tundralis Results Page Redesign Spec

Updated: 2026-03-30
Target file(s):
- `web/templates/result.html`
- `web/static/app.css`
- any server payload shaping needed to expose summary-quality fields cleanly

## Objective

Turn the current results page from a completion/artifact page into an insight page.

The current page proves the run finished.
The redesigned page should prove the product delivered value.

---

## Current diagnosis

The current `result.html` includes:
- file name
- 3 top-level stats
- top priorities ordered list
- optional segment previews
- optional segment summaries
- preview charts
- download links

That is useful but underpowered.

Current feeling:

> The job completed. Here are some outputs.

Desired feeling:

> Here is the answer, why it matters, and what to do next.

---

## Product principle

The result page should answer 4 questions immediately:
1. What happened?
2. What matters most?
3. How trustworthy is this run?
4. What should I do next?

---

## Proposed information architecture

## 1. Add a top-level executive summary hero

### Purpose
Create a strong “you got something valuable” moment the second the page loads.

### Content
- title: `Analysis complete`
- subtitle: shortened display filename
- short executive summary paragraph
- top recommendation / main takeaway
- primary CTA: `Download report`
- secondary CTA: `Download JSON`

### Suggested summary shape
Something like:
- `The strongest opportunities are [driver A], [driver B], and [driver C]. Together they represent the biggest expected lift areas for the selected outcome.`

This can be template-generated from the top 3 drivers even before richer narrative generation exists.

---

## 2. Replace plain stats row with decision-oriented summary cards

### Current stats
- rows modeled
- predictors
- R²

### Proposed stats
Keep those, but frame them better.

Suggested cards:
- `Rows modeled`
- `Drivers evaluated`
- `Model fit`
- `Top opportunity`

Optional label treatment:
- `Strong / moderate / weak fit` next to R² based on thresholding

### Why
Raw metrics are useful, but they should support decision confidence, not sit there as isolated telemetry.

---

## 3. Replace “Top priorities” list with a stronger prioritized action section

### Current issue
The ordered list is correct but visually weak.

### Proposed section
`Top actions to prioritize`

Each top driver card should show:
- driver name
- classification
- opportunity score
- impact / importance if available
- current performance if available
- one short interpretation line

### Example interpretation style
- `High impact, underperforming relative to the rest of the experience.`
- `Strong performance already; defend this strength rather than prioritize heavy investment.`

Even if this starts as rule-based copy, it will feel dramatically more productized.

---

## 4. Add a “How to read this” / confidence block

### Purpose
Users need a fast trust calibration.

### Show
- model fit metric
- rows modeled
- number of predictors
- maybe warnings if the run is thin or unstable

### Suggested framing
- `Run confidence`
- `Good directional signal`
- `Review with caution`
- `Low confidence due to small usable sample / weak fit`

### Why
This prevents over-trust and makes the app feel more mature.

---

## 5. Upgrade segment output from summary list to comparative insight

### Current issue
`Segment summaries` currently read like terse diagnostic output.

### Proposed behavior
For each segment, show:
- name
- sample size
- model fit
- top drivers
- one comparative takeaway if derivable

### Example direction
- `For Enterprise accounts, Support responsiveness matters more than for the overall sample.`
- `For New customers, onboarding clarity is the dominant driver.`

If true comparative language is not yet implemented, at least make the cards more readable and prominent.

---

## 6. Make preview charts support the story instead of floating below it

### Current issue
Preview charts are useful, but right now they are just a gallery.

### Proposed behavior
- add chart section heading tied to narrative: `Preview the key visuals`
- give each chart a friendly label if possible
- optionally pin the main action chart first

### Why
Images should feel like evidence supporting the summary, not miscellaneous artifacts.

---

## 7. Improve artifact handoff

### Current issue
The downloads work, but they feel like raw file links.

### Proposed behavior
Create a clearer deliverables area:
- `Presentation deck` — ready to share
- `Analysis JSON` — structured output for automation or QA

Optional future additions:
- generated timestamp
- methodology version
- run ID / audit metadata

### Why
This makes the output feel deliberate and premium.

---

## Proposed page structure

1. Executive summary hero
2. Decision summary cards
3. Top actions to prioritize
4. Run confidence / how to read this
5. Segment insights
6. Preview visuals
7. Deliverables

---

## Concrete implementation ideas

## A. Executive summary block

Generate from existing payload fields:
- `payload.drivers`
- `payload.model_diagnostics`
- `payload.input_summary`

Minimal viable summary logic:
- sort top drivers by opportunity rank
- take first 3
- inject into fixed narrative template

This does not require a model-generated narrative to start being useful.

---

## B. Driver action cards

For each top driver card include:
- title = `driver.driver_label`
- small meta row = classification + opportunity score
- optional badges = impact/performance quadrant if available
- single-sentence explanation from existing metrics

If supporting metrics already exist in payload, expose them more explicitly in template.
If not, start with the fields already present and extend later.

---

## C. Confidence labeling

Create a simple heuristic wrapper around R² and usable rows.

Example rough logic:
- higher R² + solid rows modeled -> `Strong directional signal`
- mid R² or limited usable rows -> `Useful, review with context`
- very low R² or thin sample -> `Low confidence`

This should be explained briefly, not academically.

---

## D. Segment cards

Each segment card should feel like a mini-result, not a log entry.

Minimum improvement:
- stronger card hierarchy
- row count and fit as badges/stats
- top drivers as chips or compact list
- optional note line

---

## E. Deliverables block

Replace plain action row with a deliverables card:
- deck description
- JSON description
- maybe `open report folder` later if local environment matters

---

## Copy direction

Use product language, not analysis-console language.

Prefer:
- `Analysis complete`
- `Top actions to prioritize`
- `Run confidence`
- `Segment insights`
- `Deliverables`

Avoid overly raw/internal feeling labels.

---

## Suggested implementation sequence

### Phase 1 — fast productization win
1. add executive summary hero
2. convert top priorities into action cards
3. add confidence block
4. restyle downloads as deliverables

### Phase 2 — richer insight framing
5. improve segment cards
6. improve chart labeling/order
7. add interpretation lines for top drivers

### Phase 3 — premium finish
8. add comparative segment commentary
9. add more deliberate methodology/run metadata
10. tune narrative quality based on real datasets

---

## Definition of done

This spec is done when:
- the result page is understandable without opening the PowerPoint
- a user can immediately see the top answer and next actions
- trust/confidence is communicated clearly
- segment outputs feel like insight, not debug summaries
- downloads feel like deliverables, not leftovers from the batch job
