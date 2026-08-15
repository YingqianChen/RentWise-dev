import { expect, test, type Page, type Route } from "@playwright/test";

import type { Dashboard, Project } from "../lib/types";

const PROJECT_ID = "project-preferences";

const initialProject: Project = {
  id: PROJECT_ID,
  user_id: "user-preferences",
  title: "Preference workflow",
  status: "active",
  max_budget: 22000,
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
    total: 0,
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
  current_advice: "",
  priority_candidates: [],
  open_investigation_items: [],
  closed_investigation_items: [],
  compare_preview: null,
  generated_at: "2026-08-15T12:00:00Z",
};

async function installApiMock(page: Page) {
  let project = initialProject;
  let updateCount = 0;
  let lastUpdate: Record<string, unknown> | null = null;

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

    if (request.method() === "PUT" && url.pathname.endsWith("/projects/" + PROJECT_ID)) {
      lastUpdate = request.postDataJSON() as Record<string, unknown>;
      updateCount += 1;
      project = {
        ...project,
        preferred_districts:
          (lastUpdate.preferred_districts as string[]) ?? project.preferred_districts,
        must_have: (lastUpdate.must_have as string[]) ?? project.must_have,
        deal_breakers: (lastUpdate.deal_breakers as string[]) ?? project.deal_breakers,
        move_in_target:
          (lastUpdate.move_in_target as string | null) ?? project.move_in_target,
        updated_at: "2026-08-15T12:05:00Z",
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(project),
      });
      return;
    }

    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Unexpected request: " + request.method() + " " + url.pathname,
      }),
    });
  });

  return {
    updateCount: () => updateCount,
    lastUpdate: () => lastUpdate,
  };
}

test("project conditions can be saved and are shown as personal fit inputs", async ({ page }) => {
  const api = await installApiMock(page);

  await page.goto("/projects/" + PROJECT_ID);
  await expect(page.getByText("Set your conditions before reviewing candidates.")).toBeVisible();
  const preferencesCard = page
    .locator("section")
    .filter({ hasText: "Set your conditions before reviewing candidates." });
  await preferencesCard.getByRole("button", { name: "Set up", exact: true }).click();

  await page.getByLabel("Preferred districts").fill("Kowloon, Wan Chai, Kowloon");
  await page.getByLabel("Target move-in date").fill("2026-06-01");
  await page.getByLabel("Must-have conditions").fill("Furnished\nNatural light");
  await page.getByLabel("Deal-breakers").fill("Shared bathroom");
  await page.getByRole("button", { name: "Save conditions" }).click();

  await expect.poll(api.updateCount).toBe(1);
  await expect.poll(() => api.lastUpdate()?.preferred_districts).toEqual(["Kowloon", "Wan Chai"]);
  await expect.poll(() => api.lastUpdate()?.move_in_target).toBe("2026-06-01");
  await expect(page.getByText("Your conditions are saved.")).toBeVisible();
  await expect(page.getByText("Preferred areas: Kowloon, Wan Chai")).toBeVisible();
});
