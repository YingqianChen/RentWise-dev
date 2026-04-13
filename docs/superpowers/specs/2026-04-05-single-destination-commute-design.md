# Single-Destination Commute Evidence Design

Date: 2026-04-05
Status: UNIMPLEMENTED — approved design draft for a future feature
Scope: Define the first commute data model and interaction flow for RentWise without turning commute into a hidden scoring engine.

## Why This Exists

RentWise currently supports candidate-pool triage and compare-driven shortlist decisions. The next commute-related work should help users answer a narrow question:

"Given my main destination, how long would each viable candidate likely take to reach?"

This design keeps commute as support evidence rather than a hard ranking layer.

## Product Decision

The first version supports exactly one project-level commute destination.

This destination is optional. Projects can still be created and used without any commute configuration.

Commute output is treated as:

- contextual evidence
- compare support
- candidate-detail support

Commute output is not treated as:

- a required project field
- a hidden weighting factor inside the main candidate assessment
- an exact truth claim when location precision is weak

## Core Principles

1. Do not manufacture fake precision.
2. Commute belongs to project context, not to the core candidate assessment score.
3. District-only data is not precise enough for commute estimation.
4. System extraction can draft location evidence, but the user must be able to correct it.
5. Compare may show commute minutes when candidates are truly comparable under the same mode and destination.

## Recommended Approach

The first implementation should follow an evidence-first path:

1. Add project-level commute preference fields.
2. Add candidate-level location evidence fields.
3. Extend extraction to draft location evidence from source text.
4. Add user correction in the candidate edit experience.
5. Return commute results as derived evidence.
6. Only after the data path is stable, connect a map-backed commute service.

This is intentionally not a map-first feature.

## Data Model

## Project-Level Fields

Add the following fields to `SearchProject`:

- `commute_enabled: bool`
- `commute_destination_label: Optional[str]`
- `commute_destination_query: Optional[str]`
- `commute_mode: Optional[str]`
- `max_commute_minutes: Optional[int]`

### Field Intent

- `commute_enabled`
  - Whether the project should attempt commute support at all.
  - Should become `true` only when the project has a usable destination and mode.

- `commute_destination_label`
  - A display-friendly destination name.
  - Example: `Central IFC`

- `commute_destination_query`
  - The original user-entered destination text.
  - Example: `Central IFC office`

- `commute_mode`
  - A single mode for the whole project to keep compare output honest.
  - Initial allowed values should be narrow, for example:
    - `transit`
    - `driving`
    - `walking`

- `max_commute_minutes`
  - Optional preference for user interpretation.
  - First version should support display and soft guidance only.
  - It should not hard-filter or auto-reject candidates.

## Candidate Location Evidence Fields

Commute requires more specific location evidence than the current `district` field.

Add the following fields to `CandidateExtractedInfo`:

- `address_text: Optional[str]`
- `building_name: Optional[str]`
- `nearest_station: Optional[str]`
- `location_confidence: str`
- `location_source: str`

### Field Intent

- `address_text`
  - Best available textual address from extraction or user correction.

- `building_name`
  - Useful when listings mention a building but not a full address.

- `nearest_station`
  - Useful for transit-oriented commute estimation when exact street address is missing.

- `location_confidence`
  - Suggested values:
    - `high`
    - `medium`
    - `low`
    - `unknown`

- `location_source`
  - Suggested values:
    - `extracted`
    - `user_corrected`
    - `mixed`
    - `unknown`

### Important Constraint

`district` remains useful for project-fit reasoning, but it must not be treated as sufficient input for route-based commute estimation.

## Derived Commute Evidence

Do not merge commute output into `CandidateAssessment` or `ComparisonService` base scoring for the first version.

Instead, define a derived response object, for example:

- `status`
- `estimated_minutes`
- `mode`
- `route_summary`
- `destination_label`
- `confidence_note`

### Suggested Status Values

- `not_configured`
- `insufficient_candidate_location`
- `ready`
- `failed`

### Why Derived Instead Of Persisted First

Commute evidence is a function of:

- the current project destination
- the current project mode
- the current candidate location evidence
- the current map provider result

That makes it better suited to a derived evidence layer in v1 than to a core persisted assessment record.

Persisting commute results can be revisited later if performance or auditability becomes a real need.

## Extraction Strategy

The system should attempt location extraction during candidate import and reassessment.

Priority order:

1. full or partial address
2. building name
3. nearest station
4. otherwise mark location as low-confidence or unknown

The extraction layer should be conservative. If the listing only hints at a broad area or uses marketing language like "near Central", the system should not overclaim that the candidate is commute-ready.

## User Correction Strategy

Candidate location should follow:

extract first, confirm when needed

This means:

- import/reassess tries to draft location evidence from text
- the candidate detail edit flow allows the user to correct location evidence
- user-corrected location should override purely extracted location for commute computation

The current candidate edit surface is the right initial correction point. A separate commute-specific editing modal is unnecessary in v1.

## Interaction Design

## Project Creation And Editing

Add an optional `Commute` section to the project form.

Fields:

- destination
- mode
- max commute minutes

Behavior:

- section should not block project creation
- if empty, commute stays disabled
- if filled, the project can start showing commute evidence where available

This keeps project creation friction low and matches RentWise's candidate-pool-first workflow.

## Candidate Import And Reassessment

After import or reassessment:

- system extracts location evidence
- system records location confidence
- candidate becomes commute-eligible only if location evidence is precise enough

The first version should not force the user to complete missing location information during import.

## Candidate Detail Page

Candidate detail should gain a small commute evidence card when a project has commute configured.

Possible states:

1. Project commute not configured
   - either hide the card or show a light prompt such as:
   - `Add a commute destination to see travel estimates.`

2. Project configured but candidate location is insufficient
   - show a clear unavailable state such as:
   - `Commute estimate unavailable: location is not precise enough yet.`
   - include a path to edit and correct location evidence

3. Commute evidence available
   - show:
     - `X min to <destination>`
     - mode
     - brief route summary
     - optional note when confidence is weaker than ideal

The card should support the main decision read, not replace it.

## Compare Page

Compare cards may display commute evidence only when the project has a configured destination.

Recommended behavior:

- display `estimated_minutes` on candidate cards when available
- display a simple unavailable state when not available
- show route mode only as supporting text
- do not use commute mode itself as a comparison axis in v1

Compare summary or key differences may mention commute only when at least two candidates have valid commute evidence under the same project mode.

## API Changes

## Project Schemas

Extend:

- `ProjectCreate`
- `ProjectUpdate`
- `ProjectResponse`
- frontend `Project`, `CreateProjectRequest`, `UpdateProjectRequest`

With:

- `commute_enabled`
- `commute_destination_label`
- `commute_destination_query`
- `commute_mode`
- `max_commute_minutes`

Validation notes:

- `commute_enabled = true` should require a destination query and commute mode
- `max_commute_minutes` should be non-negative
- empty commute configuration should be normalized cleanly instead of partially enabled

## Candidate Schemas

Extend extracted info response and internal extraction output with:

- `address_text`
- `building_name`
- `nearest_station`
- `location_confidence`
- `location_source`

## Derived Commute Endpoint Options

There are two viable API options.

### Option A: Inline Derived Evidence

Return commute evidence inside candidate detail and compare responses when applicable.

Pros:

- fewer extra requests
- easier page integration

Cons:

- more coupling between commute logic and existing read endpoints

### Option B: Dedicated Commute Read Endpoint

Examples:

- `GET /api/v1/projects/{id}/candidates/{candidateId}/commute`
- or derived commute included only in compare responses

Pros:

- clearer separation
- easier to disable or evolve

Cons:

- more frontend request orchestration

Recommendation:

Start with inline derived evidence for candidate detail and compare responses, but keep the service boundary separate so it can be extracted later.

## Service Design

Add a narrow `CommuteService`.

Suggested inputs:

- project commute configuration
- candidate location evidence

Suggested outputs:

- derived commute evidence object with status and explanation

Responsibilities:

- validate whether project commute is configured
- validate whether candidate location evidence is sufficient
- call the map provider only when prerequisites are met
- downgrade gracefully on failure

Non-responsibilities:

- it should not modify candidate assessment status
- it should not silently feed into compare ranking in v1

## Map Capability Decision

Map capability should be connected, but not as the first sub-step.

### Final Decision

Do not start by wiring the map provider before the data model and correction flow exist.

Do connect map-backed commute estimation after:

1. project commute fields exist
2. candidate location evidence fields exist
3. extraction can populate them
4. user correction is available

### Why

Without those prerequisites, the product would present commute numbers with weak grounding.

That would conflict with the current RentWise direction:

- explanation first
- visible uncertainty
- no fake precision

## Compare Logic Decision

Do not add commute minutes to `ComparisonService._compare_strength()` in v1.

Reasons:

1. commute evidence coverage will be partial at first
2. commute quality depends on location precision and provider stability
3. compare is currently framed as grouped decision support, not hidden weighted ranking

Commute may be discussed in:

- compare cards
- compare key differences
- future explanation layers

But not inside the main compare score yet.

## Failure And Uncertainty Handling

The user should always be able to tell why commute is missing or weak.

At minimum, the UI and API should distinguish:

- no project commute configured
- candidate location too weak
- map calculation failed
- commute result available but low confidence

Avoid blank states that hide the reason.

## Implementation Order

Recommended delivery sequence:

1. extend project model, schemas, and project form with commute configuration
2. extend candidate extracted info with location evidence fields
3. update extraction pipeline to draft address/building/station evidence
4. update candidate edit UI to let the user correct location evidence
5. add derived commute evidence model and UI placeholders
6. connect map MCP through a narrow `CommuteService`
7. surface commute evidence in candidate detail and compare
8. revisit persistence or scoring only after observing real data quality

## Out Of Scope For This Version

- multiple project destinations
- employer plus school combined commute logic
- commute-based auto-filtering or auto-rejection
- route-history persistence
- map-heavy visualization experience
- using commute mode as a ranked compare dimension
- district-only fallback commute estimation

## Open Questions To Revisit Later

1. Should destination parsing be persisted as a normalized canonical place object?
2. Should commute results be cached or stored after map calls are introduced?
3. Should compare eventually include a soft commute difference narrative when confidence is high?
4. Should projects later support multiple destinations with weighted priorities?

## Final Recommendation

Proceed now with commute data model and interaction design.

Do not treat map integration as the first task.

Instead:

- prepare trustworthy project and candidate inputs first
- keep commute as evidence
- add map-backed estimation only once the inputs can be corrected and explained

This is the most honest way to add commute support without weakening the current product direction.
