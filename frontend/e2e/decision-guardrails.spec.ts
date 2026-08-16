import { expect, test, type Page, type Route } from "@playwright/test";

import type { Candidate, CandidateContactPlan, CandidateFieldFact } from "../lib/types";

const PROJECT_ID = "project-e2e";
const CANDIDATE_ID = "candidate-e2e";
const SAVED_SOURCE = "Listing source: HKD 30,000 per month. Management fee not stated.";
const NOW = "2026-08-13T12:00:00Z";

const FIELD_DEFINITIONS: Array<Pick<CandidateFieldFact, "key" | "label" | "group">> = [
  { key: "monthly_rent", label: "Monthly rent", group: "monthly_cost" },
  { key: "management_fee_amount", label: "Management fee", group: "monthly_cost" },
  { key: "management_fee_included", label: "Management fee included", group: "monthly_cost" },
  { key: "rates_amount", label: "Rates amount", group: "monthly_cost" },
  { key: "rates_included", label: "Rates included", group: "monthly_cost" },
  { key: "deposit", label: "Deposit", group: "move_in_and_lease" },
  { key: "agent_fee", label: "Agent fee", group: "move_in_and_lease" },
  { key: "lease_term", label: "Lease term", group: "move_in_and_lease" },
  { key: "move_in_date", label: "Move-in date", group: "repairs_and_timing" },
  { key: "repair_responsibility", label: "Repair responsibility", group: "repairs_and_timing" },
  { key: "district", label: "District", group: "location" },
  { key: "address_text", label: "Address", group: "location" },
  { key: "building_name", label: "Building name", group: "location" },
  { key: "nearest_station", label: "Nearest station", group: "location" },
];

function unknownFieldFacts(): CandidateFieldFact[] {
  return FIELD_DEFINITIONS.map((definition) => ({
    ...definition,
    value: null,
    state: "unknown",
    confidence: "low",
    decision_usable: false,
    system_value: null,
    system_state: "unknown",
    system_confidence: "low",
    user_action: null,
    user_note: null,
    user_updated_at: null,
    evidence: [],
  }));
}

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
    field_facts: unknownFieldFacts(),
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
    field_facts: [],
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
    field_facts: candidate.field_facts.map((fact) =>
      fact.key === "monthly_rent"
        ? {
            ...fact,
            value: 30000,
            state: "explicit",
            confidence: "high",
            decision_usable: true,
            system_value: 30000,
            system_state: "explicit",
            system_confidence: "high",
            evidence: [
              {
                id: "evidence-rent",
                source_type: "listing",
                source_asset_id: null,
                source_label: "Listing text",
                quote: "HKD 30,000 per month",
                claim_value: 30000,
                claim_kind: "explicit",
                confidence: "high",
              },
            ],
          }
        : fact
    ),
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
  options: {
    importedCandidate?: Candidate;
    failFirstFieldUpdate?: boolean;
    reassessResult?: (candidate: Candidate) => Candidate;
    contactPlan?: CandidateContactPlan;
  } = {}
) {
  let currentCandidate = initialCandidate;
  let pendingReassessedCandidate: Candidate | null = null;
  let retryCount = 0;
  let fieldUpdateCount = 0;

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
      pendingReassessedCandidate = options.reassessResult?.(currentCandidate) ?? null;
      currentCandidate = {
        ...currentCandidate,
        processing_stage: "queued",
        processing_error: null,
      };
      await fulfillJson(route, currentCandidate);
      return;
    }

    if (method === "PATCH" && path.includes(`/${CANDIDATE_ID}/fields/`)) {
      const fieldKey = path.split("/").at(-1)!;
      const payload = request.postDataJSON() as {
        action: "confirm" | "correct" | "mark_unknown" | "revert";
        value?: unknown;
        note?: string;
      };
      fieldUpdateCount += 1;
      if (options.failFirstFieldUpdate && fieldUpdateCount === 1) {
        await fulfillJson(route, { detail: "Temporary field update failure." }, 409);
        return;
      }
      currentCandidate = {
        ...currentCandidate,
        field_facts: currentCandidate.field_facts.map((fact) => {
          if (fact.key !== fieldKey) return fact;
          if (payload.action === "revert") {
            return {
              ...fact,
              value: fact.system_value,
              state: fact.system_state,
              decision_usable: fact.system_state === "explicit",
              user_action: null,
              user_note: null,
              user_updated_at: null,
            };
          }
          if (payload.action === "mark_unknown") {
            return {
              ...fact,
              value: null,
              state: "user_marked_unknown",
              decision_usable: false,
              user_action: "marked_unknown",
              user_note: payload.note ?? null,
              user_updated_at: NOW,
            };
          }
          const value = payload.action === "correct" ? payload.value : fact.system_value;
          return {
            ...fact,
            value,
            state: payload.action === "correct" ? "user_corrected" : "user_confirmed",
            decision_usable: true,
            user_action: payload.action === "correct" ? "corrected" : "confirmed",
            user_note: payload.note ?? null,
            user_updated_at: NOW,
          };
        }),
      };
      if (fieldKey === "monthly_rent" && currentCandidate.extracted_info) {
        const updatedFact = currentCandidate.field_facts.find((fact) => fact.key === fieldKey)!;
        currentCandidate = {
          ...currentCandidate,
          extracted_info: {
            ...currentCandidate.extracted_info,
            monthly_rent: updatedFact.value === null ? null : String(updatedFact.value),
          },
        };
      }
      await fulfillJson(route, currentCandidate);
      return;
    }

    if (method === "GET" && path.endsWith(`/candidates/${CANDIDATE_ID}`)) {
      if (pendingReassessedCandidate) {
        currentCandidate = pendingReassessedCandidate;
        pendingReassessedCandidate = null;
      }
      await fulfillJson(route, currentCandidate);
      return;
    }

    if (method === "POST" && path.endsWith(`/candidates/${CANDIDATE_ID}/contact-plan`)) {
      await fulfillJson(
        route,
        options.contactPlan ?? {
          contact_goal: "Clarify the remaining questions before deciding.",
          questions: ["Could you confirm the exact monthly rent?"],
          message_draft: "Hi, could you confirm the exact monthly rent?",
          questions_zh: ["請確認每月實際租金是多少？"],
          message_draft_zh: "你好，請確認每月實際租金是多少？謝謝！",
        }
      );
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
    fieldUpdateCount: () => fieldUpdateCount,
  };
}

test("import failure keeps the source and offers a clean retry path", async ({ page }) => {
  const failed = failedCandidate();
  const api = await installApiMock(page, failed, { importedCandidate: failed });

  await page.goto(`/projects/${PROJECT_ID}/import`);
  await page
    .getByPlaceholder("Paste the property ad or listing details here...")
    .fill(SAVED_SOURCE);
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
  await expect(page.locator("textarea").first()).toHaveValue(SAVED_SOURCE);
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

test("contact draft can switch between English and Traditional Chinese", async ({ page }) => {
  const candidate = baseCandidate({ name: "Bilingual contact case" });
  await installApiMock(page, candidate, {
    contactPlan: {
      contact_goal: "Clarify the remaining questions before deciding.",
      questions: ["Could you confirm the exact monthly rent?"],
      message_draft: "Hi, could you confirm the exact monthly rent?",
      questions_zh: ["請確認每月實際租金是多少？"],
      message_draft_zh: "你好，請確認每月實際租金是多少？謝謝！",
    },
  });

  await page.goto(`/projects/${PROJECT_ID}/candidates/${CANDIDATE_ID}`);
  await expect(page.getByText("Outreach draft")).toBeVisible();
  await page.getByRole("button", { name: "Draft outreach" }).click();
  await expect(page.getByText("Hi, could you confirm the exact monthly rent?")).toBeVisible();

  await page.getByRole("button", { name: "繁體中文" }).click();
  await expect(page.getByText("繁體中文訊息草稿")).toBeVisible();
  await expect(page.getByText("你好，請確認每月實際租金是多少？謝謝！")).toBeVisible();
  await expect(page.getByText("請確認每月實際租金是多少？", { exact: true })).toBeVisible();
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
  const rentCard = page.locator("article").filter({ hasText: "Monthly rent" }).first();
  await rentCard.getByText("View 1 source quote").click();
  await expect(rentCard.getByText("HKD 30,000 per month")).toBeVisible();
});

test("inferred field can be confirmed and corrected with its source still visible", async ({ page }) => {
  const candidate = baseCandidate({
    name: "Field review case",
    field_facts: unknownFieldFacts().map((fact) =>
      fact.key === "monthly_rent"
        ? {
            ...fact,
            value: 18000,
            state: "inferred",
            confidence: "medium",
            system_value: 18000,
            system_state: "inferred",
            system_confidence: "medium",
            evidence: [
              {
                id: "inferred-rent",
                source_type: "chat",
                source_asset_id: null,
                source_label: "Chat",
                quote: "Around eighteen thousand, I think",
                claim_value: 18000,
                claim_kind: "inferred",
                confidence: "medium",
              },
            ],
          }
        : fact
    ),
  });
  const api = await installApiMock(page, candidate);

  await page.goto(`/projects/${PROJECT_ID}/candidates/${CANDIDATE_ID}`);
  const rentCard = page.locator("article").filter({ hasText: "Monthly rent" }).filter({ hasText: "System inferred" }).first();
  await expect(page.getByText("System inferred")).toBeVisible();
  await page.getByText("View 1 source quote").click();
  await expect(page.getByText("Around eighteen thousand, I think")).toBeVisible();
  await page.getByRole("button", { name: "Confirm" }).first().click();
  await expect.poll(api.fieldUpdateCount).toBe(1);
  await expect(page.getByText("You confirmed", { exact: true })).toBeVisible();

  const confirmedRentCard = page.locator("article").filter({ hasText: "Monthly rent" }).filter({ hasText: "You confirmed" }).first();
  await confirmedRentCard.getByRole("button", { name: "Correct" }).click();
  await confirmedRentCard.getByLabel("Correct value").fill("19000");
  await confirmedRentCard.getByRole("button", { name: "Save correction" }).click();
  await expect.poll(api.fieldUpdateCount).toBe(2);
  await expect(page.getByText("You corrected")).toBeVisible();
  await expect(page.getByText("HKD 19,000")).toBeVisible();

  const correctedRentCard = page.locator("article").filter({ hasText: "Monthly rent" }).filter({ hasText: "You corrected" }).first();
  await correctedRentCard.getByRole("button", { name: "Mark unknown" }).click();
  await expect.poll(api.fieldUpdateCount).toBe(3);
  await expect(page.getByText("You marked unknown")).toBeVisible();
  await expect(page.getByText("Not confirmed").first()).toBeVisible();

  const unknownRentCard = page.locator("article").filter({ hasText: "Monthly rent" }).filter({ hasText: "You marked unknown" }).first();
  await unknownRentCard.getByRole("button", { name: "Restore system value" }).click();
  await expect.poll(api.fieldUpdateCount).toBe(4);
  await expect(page.getByText("System inferred")).toBeVisible();
  await expect(page.getByText("HKD 18,000")).toBeVisible();
});

test("field update error stays on the card and can be retried", async ({ page }) => {
  const candidate = baseCandidate({
    name: "Field error recovery case",
    field_facts: unknownFieldFacts().map((fact) =>
      fact.key === "monthly_rent"
        ? {
            ...fact,
            value: 18000,
            state: "inferred",
            confidence: "medium",
            system_value: 18000,
            system_state: "inferred",
            system_confidence: "medium",
          }
        : fact
    ),
  });
  const api = await installApiMock(page, candidate, { failFirstFieldUpdate: true });

  await page.goto(`/projects/${PROJECT_ID}/candidates/${CANDIDATE_ID}`);
  const rentCard = page.locator("article").filter({ hasText: "Monthly rent" }).first();
  await rentCard.getByRole("button", { name: "Confirm" }).click();
  await expect(rentCard.getByText("Temporary field update failure.")).toBeVisible();
  await expect.poll(api.fieldUpdateCount).toBe(1);

  await rentCard.getByRole("button", { name: "Confirm" }).click();
  await expect.poll(api.fieldUpdateCount).toBe(2);
  await expect(page.getByText("You confirmed", { exact: true })).toBeVisible();
});

test("conflicting source claims can be reviewed and resolved", async ({ page }) => {
  const candidate = baseCandidate({
    name: "Conflicting rent case",
    field_facts: unknownFieldFacts().map((fact) =>
      fact.key === "monthly_rent"
        ? {
            ...fact,
            state: "conflicted",
            system_state: "conflicted",
            evidence: [
              {
                id: "listing-rent",
                source_type: "listing",
                source_asset_id: null,
                source_label: "Listing text",
                quote: "Monthly rent HKD 18,000",
                claim_value: 18000,
                claim_kind: "explicit",
                confidence: "high",
              },
              {
                id: "chat-rent",
                source_type: "chat",
                source_asset_id: null,
                source_label: "Agent chat",
                quote: "The updated rent is HKD 19,000",
                claim_value: 19000,
                claim_kind: "explicit",
                confidence: "high",
              },
            ],
          }
        : fact
    ),
  });
  const api = await installApiMock(page, candidate);

  await page.goto(`/projects/${PROJECT_ID}/candidates/${CANDIDATE_ID}`);
  const rentCard = page.locator("article").filter({ hasText: "Monthly rent" }).first();
  await expect(rentCard.getByText("Sources conflict", { exact: true })).toBeVisible();
  await rentCard.getByText("View 2 source quotes").click();
  await expect(rentCard.getByText("Monthly rent HKD 18,000")).toBeVisible();
  await expect(rentCard.getByText("The updated rent is HKD 19,000")).toBeVisible();
  await expect(rentCard.getByText("Claimed value: HKD 18,000")).toBeVisible();
  await expect(rentCard.getByText("Claimed value: HKD 19,000")).toBeVisible();

  await rentCard.getByRole("button", { name: "Correct" }).click();
  await rentCard.getByLabel("Correct value").fill("18500");
  await rentCard.getByRole("button", { name: "Save correction" }).click();
  await expect.poll(api.fieldUpdateCount).toBe(1);
  await expect(page.getByText("You corrected", { exact: true })).toBeVisible();
  await expect(page.getByText("HKD 18,500")).toBeVisible();
});

test("reassessment refreshes source evidence without overwriting a user correction", async ({ page }) => {
  const candidate = baseCandidate({
    name: "Correction survives reassessment",
    field_facts: unknownFieldFacts().map((fact) =>
      fact.key === "monthly_rent"
        ? {
            ...fact,
            value: 18000,
            state: "explicit",
            confidence: "high",
            decision_usable: true,
            system_value: 18000,
            system_state: "explicit",
            system_confidence: "high",
            evidence: [
              {
                id: "old-rent",
                source_type: "listing",
                source_asset_id: null,
                source_label: "Listing text",
                quote: "Original rent HKD 18,000",
                claim_value: 18000,
                claim_kind: "explicit",
                confidence: "high",
              },
            ],
          }
        : fact
    ),
  });
  const api = await installApiMock(page, candidate, {
    reassessResult: (current) => ({
      ...current,
      processing_stage: "completed",
      field_facts: current.field_facts.map((fact) =>
        fact.key === "monthly_rent"
          ? {
              ...fact,
              system_value: 19000,
              system_state: "explicit",
              system_confidence: "high",
              evidence: [
                {
                  id: "updated-rent",
                  source_type: "listing",
                  source_asset_id: null,
                  source_label: "Listing text",
                  quote: "Updated listing rent HKD 19,000",
                  claim_value: 19000,
                  claim_kind: "explicit",
                  confidence: "high",
                },
              ],
            }
          : fact
      ),
    }),
  });

  await page.goto(`/projects/${PROJECT_ID}/candidates/${CANDIDATE_ID}`);
  const rentCard = page.locator("article").filter({ hasText: "Monthly rent" }).first();
  await rentCard.getByRole("button", { name: "Correct" }).click();
  await rentCard.getByLabel("Correct value").fill("17500");
  await rentCard.getByRole("button", { name: "Save correction" }).click();
  await expect(page.getByText("You corrected", { exact: true })).toBeVisible();
  await expect(page.getByText("HKD 17,500")).toBeVisible();

  await page.getByRole("button", { name: "Reassess", exact: true }).click();
  await expect.poll(api.retryCount).toBe(1);
  const reassessedRentCard = page.locator("article").filter({ hasText: "Monthly rent" }).first();
  await expect(reassessedRentCard.getByText("You corrected", { exact: true })).toBeVisible();
  await expect(reassessedRentCard.getByText("HKD 17,500")).toBeVisible();
  await reassessedRentCard.getByText("View 1 source quote").click();
  await expect(reassessedRentCard.getByText("Updated listing rent HKD 19,000")).toBeVisible();
  await expect(reassessedRentCard.getByText("Original rent HKD 18,000")).toHaveCount(0);
});
