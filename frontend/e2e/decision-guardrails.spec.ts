import { expect, test, type Page, type Route } from "@playwright/test";

import type { Candidate } from "../lib/types";

const PROJECT_ID = "project-e2e";
const CANDIDATE_ID = "candidate-e2e";
const SAVED_SOURCE = "Listing source: HKD 30,000 per month. Management fee not stated.";
const NOW = "2026-08-13T12:00:00Z";

function baseCandidate(overrides: Partial<Candidate> = {}): Candidate {
  return {
    id: CANDIDATE_ID,
    project_id: PROJECT_ID,
    name: "Browser test candidate",
    source_type: "manual_text",
    raw_listing_text: SAVED_SOURCE,
    raw_chat_text: null,
    raw_note_text: null,
    combined_text: SAVED_SOURCE,
    status: "needs_info",
    processing_stage: "completed",
    processing_error: null,
    user_decision: "undecided",
    created_at: NOW,
    updated_at: NOW,
    extracted_info: {
      candidate_id: CANDIDATE_ID,
      monthly_rent: null,
      management_fee_amount: null,
      management_fee_included: null,
      rates_amount: null,
      rates_included: null,
      deposit: null,
      agent_fee: null,
      lease_term: null,
      move_in_date: null,
      repair_responsibility: null,
      district: null,
      furnished: null,
      size_sqft: null,
      bedrooms: null,
      suspected_sdu: null,
      sdu_detection_reason: null,
      address_text: null,
      building_name: null,
      nearest_station: null,
      location_confidence: "unknown",
      location_source: "none",
      decision_signals: [],
      raw_facts: [],
      ocr_texts: [],
    },
    cost_assessment: {
      candidate_id: CANDIDATE_ID,
      known_monthly_cost: null,
      monthly_cost_confidence: "low",
      monthly_cost_missing_items: ["monthly rent", "management fee", "rates"],
      move_in_cost_known_part: null,
      move_in_cost_confidence: "low",
      cost_risk_flag: "incomplete",
      summary: "The monthly cost is not yet known.",
    },
    clause_assessment: {
      candidate_id: CANDIDATE_ID,
      repair_responsibility_level: "unknown",
      lease_term_level: "unknown",
      move_in_date_level: "unknown",
      clause_confidence: "low",
      clause_risk_flag: "needs_confirmation",
      summary: "The lease terms still need confirmation.",
      legal_references: [],
    },
    candidate_assessment: {
      candidate_id: CANDIDATE_ID,
      top_level_recommendation: "not_ready",
      potential_value_level: "unknown",
      completeness_level: "low",
      critical_uncertainty_level: "high",
      decision_risk_level: "unknown",
      information_gain_level: "high",
      recommendation_confidence: "low",
      next_best_action: "verify_cost",
      status: "needs_info",
      labels: ["Information incomplete"],
      summary: "There is not enough verified information to make a decision.",
    },
    benchmark: null,
    commute_evidence: null,
    source_assets: [],
    ...overrides,
  };
}

function failedCandidate(): Candidate {
  return baseCandidate({
    name: "Imported failure case",
    status: "needs_info",
    processing_stage: "failed",
    processing_error: "The analysis service stopped before producing a result.",
    extracted_info: null,
    cost_assessment: null,
    clause_assessment: null,
    candidate_assessment: null,
  });
}

function overBudgetCandidate(): Candidate {
  const candidate = baseCandidate({
    name: "Source-backed over-budget case",
    status: "recommended_reject",
  });

  return {
    ...candidate,
    extracted_info: {
      ...candidate.extracted_info!,
      monthly_rent: "30000",
      raw_facts: ["Monthly rent: HKD 30,000"],
    },
    cost_assessment: {
      ...candidate.cost_assessment!,
      known_monthly_cost: 30000,
      monthly_cost_confidence: "high",
      monthly_cost_missing_items: [],
      move_in_cost_known_part: 60000,
      move_in_cost_confidence: "medium",
      cost_risk_flag: "over_budget",
      summary: "The source explicitly states HKD 30,000, above the user's HKD 25,000 budget.",
    },
    candidate_assessment: {
      ...candidate.candidate_assessment!,
      top_level_recommendation: "likely_reject",
      potential_value_level: "low",
      completeness_level: "medium",
      critical_uncertainty_level: "low",
      decision_risk_level: "high",
      information_gain_level: "low",
      recommendation_confidence: "high",
      next_best_action: "reject",
      status: "recommended_reject",
      labels: ["Over budget"],
      summary: "The verified rent is above the user's stated budget.",
    },
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installApiMock(
  page: Page,
  initialCandidate: Candidate,
  options: { importedCandidate?: Candidate } = {}
) {
  let currentCandidate = initialCandidate;
  let retryCount = 0;

  await page.addInitScript(() => {
    window.localStorage.setItem("rentwise_token", "browser-test-token");
  });

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();

    if (method === "POST" && path.endsWith("/candidates/import")) {
      currentCandidate = options.importedCandidate ?? currentCandidate;
      await fulfillJson(route, {
        ...currentCandidate,
        processing_stage: "queued",
        processing_error: null,
      });
      return;
    }

    if (method === "POST" && path.endsWith(`/${CANDIDATE_ID}/reassess`)) {
      retryCount += 1;
      currentCandidate = {
        ...currentCandidate,
        processing_stage: "queued",
        processing_error: null,
      };
      await fulfillJson(route, currentCandidate);
      return;
    }

    if (method === "GET" && path.endsWith(`/candidates/${CANDIDATE_ID}`)) {
      await fulfillJson(route, currentCandidate);
      return;
    }

    if (method === "GET" && path.endsWith("/candidates")) {
      await fulfillJson(route, { candidates: [currentCandidate], total: 1 });
      return;
    }

    await fulfillJson(route, { detail: `Unexpected browser-test request: ${method} ${path}` }, 500);
  });

  return {
    retryCount: () => retryCount,
  };
}

test("import failure keeps the source and offers a clean retry path", async ({ page }) => {
  const failed = failedCandidate();
  const api = await installApiMock(page, failed, { importedCandidate: failed });

  await page.goto(`/projects/${PROJECT_ID}/import`);
  await page.getByLabel("Listing text").fill(SAVED_SOURCE);
  await page.getByRole("button", { name: "Save and start analysis" }).click();

  await expect(page).toHaveURL(
    new RegExp(`/projects/${PROJECT_ID}/candidates/${CANDIDATE_ID}$`)
  );
  await expect(page.getByRole("heading", { name: "Imported failure case" })).toBeVisible();
  await expect(page.getByText("Import needs attention")).toBeVisible();
  await expect(page.getByText("Your source information is still saved.", { exact: false })).toBeVisible();

  await expect(page.getByText("What matters now")).toHaveCount(0);
  await expect(page.getByText("Outreach draft")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Shortlist" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Reject" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Compare unavailable" })).toBeDisabled();

  await page.getByRole("button", { name: "Edit source information" }).first().click();
  await expect(page.getByLabel("Listing text")).toHaveValue(SAVED_SOURCE);
  await page.getByRole("button", { name: "Close editor" }).click();

  await page.getByRole("button", { name: "Retry analysis" }).first().click();
  await expect.poll(api.retryCount).toBe(1);
  await expect(page.getByText("Queued for background analysis")).toBeVisible();
});

test("all unknown evidence stays not ready and is never presented as a rejection", async ({ page }) => {
  const candidate = baseCandidate({ name: "All unknown case" });
  await installApiMock(page, candidate);

  await page.goto(`/projects/${PROJECT_ID}/candidates/${CANDIDATE_ID}`);

  await expect(page.getByRole("heading", { name: "All unknown case" })).toBeVisible();
  await expect(page.getByText("System: not ready")).toBeVisible();
  await expect(page.getByText("There is not enough verified information to make a decision.")).toBeVisible();
  await expect(page.getByText("System: likely reject")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Shortlist" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Reject" })).toBeEnabled();
});

test("explicit source-backed over-budget evidence can produce likely reject", async ({ page }) => {
  const candidate = overBudgetCandidate();
  await installApiMock(page, candidate);

  await page.goto(`/projects/${PROJECT_ID}/candidates/${CANDIDATE_ID}`);

  await expect(page.getByRole("heading", { name: "Source-backed over-budget case" })).toBeVisible();
  await expect(page.getByText("System: likely reject")).toBeVisible();
  await expect(page.getByText("HKD 30,000").first()).toBeVisible();
  await expect(page.getByText("The verified rent is above the user's stated budget.")).toBeVisible();
  await expect(page.getByText("System: not ready")).toHaveCount(0);
});
