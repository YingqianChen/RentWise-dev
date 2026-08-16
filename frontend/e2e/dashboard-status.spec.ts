import { expect, test, type Page, type Route } from "@playwright/test";

import type { Dashboard, Project } from "../lib/types";

const PROJECT_ID = "dashboard-status";

const project: Project = {
  id: PROJECT_ID,
  user_id: "user-dashboard-status",
  title: "Dashboard status workflow",
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
  created_at: "2026-08-15T12:00:00Z",
  updated_at: "2026-08-15T12:00:00Z",
};

const dashboard: Dashboard = {
  project_id: PROJECT_ID,
  stats: {
    total: 2,
    new: 0,
    needs_info: 0,
    follow_up: 0,
    high_risk_pending: 0,
    recommended_reject: 0,
    shortlisted: 0,
    rejected: 0,
    processing: 1,
    analysis_failed: 1,
  },
  current_advice: "One candidate still needs attention.",
  priority_candidates: [],
  open_investigation_items: [],
  closed_investigation_items: [],
  compare_preview: null,
  generated_at: "2026-08-15T12:00:00Z",
};

const candidates = [
  {
    id: "processing-candidate",
    project_id: PROJECT_ID,
    name: "Processing candidate",
    processing_stage: "assessing",
    processing_error: null,
    extracted_info: null,
    commute_evidence: null,
    candidate_assessment: null,
    user_decision: "undecided",
  },
  {
    id: "failed-candidate",
    project_id: PROJECT_ID,
    name: "Failed candidate",
    processing_stage: "failed",
    processing_error: "The analysis service stopped before producing a result.",
    extracted_info: null,
    commute_evidence: null,
    candidate_assessment: null,
    user_decision: "undecided",
  },
];

async function installApiMock(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("rentwise_token", "browser-test-token");
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET" && path.endsWith("/projects/" + PROJECT_ID)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(project) });
      return;
    }
    if (request.method() === "GET" && path.endsWith("/projects/" + PROJECT_ID + "/dashboard")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(dashboard) });
      return;
    }
    if (request.method() === "GET" && path.endsWith("/projects/" + PROJECT_ID + "/candidates")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ candidates, total: candidates.length }),
      });
      return;
    }
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Unexpected request" }) });
  });
}

test("Dashboard separates processing from failed candidates", async ({ page }) => {
  await installApiMock(page);

  await page.goto("/projects/" + PROJECT_ID);
  await expect(page.getByRole("link", { name: "Processing candidate", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Failed candidate", exact: true })).toBeVisible();

  const processingCard = page.locator("div.rounded-xl").filter({ hasText: "Processing candidate" }).first();
  const failedCard = page.locator("div.rounded-xl").filter({ hasText: "Failed candidate" }).first();
  await expect(processingCard.getByText("Processing", { exact: true })).toBeVisible();
  await expect(failedCard.getByText("Needs attention", { exact: true })).toBeVisible();
  await expect(failedCard.getByText("Processing", { exact: true })).toHaveCount(0);
});
