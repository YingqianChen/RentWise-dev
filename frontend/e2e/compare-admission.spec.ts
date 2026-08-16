import { expect, test, type Page, type Route } from "@playwright/test";

const PROJECT_ID = "compare-admission";

const project = {
  id: PROJECT_ID,
  user_id: "user-compare-admission",
  title: "Compare admission workflow",
  status: "active",
  max_budget: null,
  preferred_districts: [],
  must_have: [],
  deal_breakers: [],
  move_in_target: null,
  notes: null,
  commute_enabled: false,
  commute_destination_label: null,
  commute_destination_query: null,
  commute_mode: null,
  max_commute_minutes: null,
  commute_destination_lat: null,
  commute_destination_lng: null,
  commute_departure_window: "peak_both",
  commute_departure_time: null,
  created_at: "2026-08-16T12:00:00Z",
  updated_at: "2026-08-16T12:00:00Z",
};

const candidates = Array.from({ length: 6 }, (_, index) => ({
  id: `compare-candidate-${index + 1}`,
  project_id: PROJECT_ID,
  name: `Candidate ${index + 1}`,
  processing_stage: "completed",
  processing_error: null,
  extracted_info: null,
  commute_evidence: null,
  candidate_assessment: null,
  user_decision: "undecided",
}));

const dashboard = {
  project_id: PROJECT_ID,
  stats: {
    total: candidates.length,
    new: 0,
    needs_info: 0,
    follow_up: 0,
    high_risk_pending: 0,
    recommended_reject: 0,
    shortlisted: 0,
    rejected: 0,
    processing: 0,
    analysis_failed: 0,
  },
  current_advice: null,
  priority_candidates: [],
  open_investigation_items: [],
  closed_investigation_items: [],
  compare_preview: null,
  generated_at: "2026-08-16T12:00:00Z",
};

function compareCard(
  candidateId: string,
  name: string,
  compareGroup: "best_current_option" | "viable_alternative",
  decisionConfidence: "high" | "medium"
) {
  return {
    candidate_id: candidateId,
    name,
    compare_group: compareGroup,
    top_recommendation: "shortlist_recommendation",
    decision_confidence: decisionConfidence,
    evidence_summary: {
      explicit_count: 8,
      inferred_count: 1,
      unresolved_count: 5,
      conflicted_count: 0,
      source_labels: ["Listing text"],
    },
    decision_explanation: `${name} has a clear compare explanation.`,
    main_tradeoff: "One tradeoff still needs attention.",
    open_blocker: null,
    next_action: "schedule_viewing",
    monthly_rent: null,
    district: null,
    status: "follow_up",
    user_decision: "undecided",
    benchmark: null,
    commute_evidence: null,
  };
}

const comparison = {
  project_id: PROJECT_ID,
  selected_count: 2,
  summary: {
    headline: "Candidate 1 is the strongest current option",
    summary: "Candidate 1 is currently easier to trust.",
    confidence_note: "This is a working comparison, not a final verdict.",
  },
  agent_briefing: {
    current_take: "Candidate 1 is the current lead.",
    why_now: "It is easier to trust today.",
    what_could_change: "Candidate 2 could still move up with more evidence.",
    today_s_move: "Contact Candidate 1 first.",
    confidence_note: "This is a working comparison, not a final verdict.",
  },
  groups: {
    best_current_option: compareCard(
      "compare-candidate-1",
      "Candidate 1",
      "best_current_option",
      "high"
    ),
    viable_alternatives: [
      compareCard(
        "compare-candidate-2",
        "Candidate 2",
        "viable_alternative",
        "medium"
      ),
    ],
    not_ready_for_fair_comparison: [],
    likely_drop: [],
  },
  key_differences: [],
  recommended_next_actions: {
    contact_first: null,
    questions_to_ask: [],
    viewing_candidate: null,
    deprioritize: [],
  },
  generated_at: "2026-08-16T12:00:00Z",
};

async function installApiMock(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("rentwise_token", "browser-test-token");
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET" && path.endsWith(`/projects/${PROJECT_ID}`)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(project),
      });
      return;
    }
    if (request.method() === "GET" && path.endsWith(`/projects/${PROJECT_ID}/dashboard`)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(dashboard),
      });
      return;
    }
    if (request.method() === "GET" && path.endsWith(`/projects/${PROJECT_ID}/candidates`)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ candidates, total: candidates.length }),
      });
      return;
    }
    if (request.method() === "POST" && path.endsWith(`/projects/${PROJECT_ID}/compare`)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(comparison),
      });
      return;
    }
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Unexpected request" }),
    });
  });
}

test("Dashboard caps a compare set at five candidates", async ({ page }) => {
  await installApiMock(page);
  await page.goto(`/projects/${PROJECT_ID}`);

  for (let index = 1; index <= 5; index += 1) {
    await page.getByRole("checkbox", { name: `Candidate ${index} for comparison` }).check();
  }

  await expect(page.getByText("5 / 5 selected", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Maximum 5 candidates — remove one before adding another.", { exact: true })
  ).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "Candidate 6 for comparison" })
  ).toBeDisabled();

  await page.getByRole("checkbox", { name: "Candidate 1 for comparison" }).uncheck();
  await page.getByRole("checkbox", { name: "Candidate 6 for comparison" }).check();
  await expect(page.getByText("5 / 5 selected", { exact: true })).toBeVisible();
});

test("Compare workspace shows decision confidence", async ({ page }) => {
  await installApiMock(page);
  await page.goto(
    `/projects/${PROJECT_ID}/compare?ids=compare-candidate-1,compare-candidate-2`
  );

  await expect(page.getByText("Decision confidence: High", { exact: true })).toBeVisible();
  await expect(page.getByText("Decision confidence: Medium", { exact: true })).toBeVisible();
});
