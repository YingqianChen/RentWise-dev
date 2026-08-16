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
