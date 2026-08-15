import { expect, test, type Page, type Route } from "@playwright/test";

import type { Dashboard, InvestigationItem, Project } from "../lib/types";

const PROJECT_ID = "investigation-actions";

const project: Project = {
  id: PROJECT_ID,
  user_id: "user-investigation",
  title: "Investigation workflow",
  status: "active",
  max_budget: 22000,
  preferred_districts: ["Wan Chai"],
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

const openItem: InvestigationItem = {
  id: "task-1",
  candidate_id: null,
  category: "cost",
  title: "Confirm the quoted rent for Flat A",
  question: "Ask for the rent in writing.",
  priority: "high",
  status: "open",
  note: null,
};

const dashboardBase: Dashboard = {
  project_id: PROJECT_ID,
  stats: {
    total: 1,
    new: 0,
    needs_info: 1,
    follow_up: 0,
    high_risk_pending: 0,
    recommended_reject: 0,
    shortlisted: 0,
    rejected: 0,
    processing: 0,
    analysis_failed: 0,
  },
  current_advice: "Confirm the remaining cost details.",
  priority_candidates: [],
  open_investigation_items: [openItem],
  closed_investigation_items: [],
  compare_preview: null,
  generated_at: "2026-08-15T12:00:00Z",
};

async function installApiMock(page: Page) {
  let dashboard = dashboardBase;
  let lastPatch: Record<string, unknown> | null = null;

  await page.addInitScript(() => {
    window.localStorage.setItem("rentwise_token", "browser-test-token");
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === "GET" && url.pathname.endsWith("/projects/" + PROJECT_ID)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(project),
      });
      return;
    }

    if (
      request.method() === "GET" &&
      url.pathname.endsWith("/projects/" + PROJECT_ID + "/dashboard")
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(dashboard),
      });
      return;
    }

    if (
      request.method() === "GET" &&
      url.pathname.endsWith("/projects/" + PROJECT_ID + "/candidates")
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ candidates: [], total: 0 }),
      });
      return;
    }

    if (
      request.method() === "PATCH" &&
      url.pathname.endsWith("/projects/" + PROJECT_ID + "/investigation/items/task-1")
    ) {
      lastPatch = request.postDataJSON() as Record<string, unknown>;
      const status = lastPatch.status as InvestigationItem["status"];
      const updatedItem: InvestigationItem = {
        ...openItem,
        status,
        note: (lastPatch.note as string | null) ?? null,
      };
      dashboard = {
        ...dashboard,
        open_investigation_items: status === "open" ? [updatedItem] : [],
        closed_investigation_items: status === "open" ? [] : [updatedItem],
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(updatedItem),
      });
      return;
    }

    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Unexpected request: " + request.method() + " " + url.pathname }),
    });
  });

  return {
    lastPatch: () => lastPatch,
  };
}

test("investigation items can be noted, closed, and reopened", async ({ page }) => {
  const api = await installApiMock(page);

  await page.goto("/projects/" + PROJECT_ID);
  await expect(page.getByText(openItem.title)).toBeVisible();

  await page.getByLabel(`Note for ${openItem.title}`).fill("Landlord replied in WhatsApp.");
  await page.getByRole("button", { name: "Save note" }).click();
  await expect.poll(() => api.lastPatch()?.note).toBe("Landlord replied in WhatsApp.");
  await expect(page.getByText("Landlord replied in WhatsApp.")).toBeVisible();

  await page.getByRole("button", { name: "Mark resolved" }).click();
  await expect.poll(() => api.lastPatch()?.status).toBe("resolved");
  await expect(page.getByText("Recorded items")).toBeVisible();
  await expect(page.getByText("Resolved")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reopen" })).toBeVisible();

  await page.getByRole("button", { name: "Reopen" }).click();
  await expect.poll(() => api.lastPatch()?.status).toBe("open");
  await expect(page.getByRole("button", { name: "Mark resolved" })).toBeVisible();
});
