import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const TOKEN = "synthetic-session-token";

async function seed(page: Page) {
  await page.goto("/");
  await page.evaluate((token) => localStorage.setItem("rentwise_token", token), TOKEN);
}

async function stubApi(context: BrowserContext) {
  await context.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/me") {
      return route.fulfill({ json: { id: "session-user", email: "session@example.com", created_at: "2026-09-09T00:00:00Z" } });
    }
    if (path === "/api/v1/projects") return route.fulfill({ json: { projects: [], total: 0 } });
    if (path === "/api/v1/auth/logout") return route.fulfill({ status: 204 });
    return route.fulfill({ status: 404, json: { detail: "Unexpected test route" } });
  });
}

test("sign out revokes the session before clearing it and updates another open tab", async ({ page, context }) => {
  await stubApi(context);
  let revoked = false;
  await context.route("**/api/v1/auth/logout", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers().authorization).toBe(`Bearer ${TOKEN}`);
    expect(await page.evaluate(() => localStorage.getItem("rentwise_token"))).toBe(TOKEN);
    revoked = true;
    await route.fulfill({ status: 204 });
  });
  await seed(page);
  await page.goto("/projects");
  const other = await context.newPage();
  await other.goto("/projects");
  await expect(other.getByRole("heading", { name: "Search projects" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(other).toHaveURL(/\/login$/);
  expect(revoked).toBe(true);
  expect(await page.evaluate(() => localStorage.getItem("rentwise_token"))).toBeNull();
});

test("failed sign out stays signed in and can be retried", async ({ page, context }) => {
  await stubApi(context);
  let attempts = 0;
  await context.route("**/api/v1/auth/logout", (route) => {
    attempts += 1;
    return attempts === 1
      ? route.fulfill({ status: 503, json: { detail: "Temporarily unavailable" } })
      : route.fulfill({ status: 204 });
  });
  await seed(page);
  await page.goto("/projects");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Please retry to finish signing out");
  expect(await page.evaluate(() => localStorage.getItem("rentwise_token"))).toBe(TOKEN);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("expired session leaves a nested page and returns to login without looping", async ({ page, context }) => {
  await stubApi(context);
  await context.route("**/api/v1/projects/expired-project", (route) => route.fulfill({ status: 401, json: { detail: "Invalid or expired token" } }));
  await seed(page);
  await page.goto("/projects/expired-project");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("rentwise_token"))).toBeNull();
});

for (const status of [403, 429, 503]) {
  test(`${status} while loading projects does not sign out or pretend there are no projects`, async ({ page, context }) => {
    await stubApi(context);
    let calls = 0;
    await context.route("**/api/v1/projects", (route) => {
      calls += 1;
      return calls === 1
        ? route.fulfill({ status, json: { detail: "Please retry this request" } })
        : route.fulfill({ json: { projects: [], total: 0 } });
    });
    await seed(page);
    await page.goto("/projects");
    await expect(page.locator("main").getByRole("alert")).toHaveText("Please retry this request");
    await expect(page.getByRole("heading", { name: "No projects yet" })).not.toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem("rentwise_token"))).toBe(TOKEN);
    await page.getByRole("button", { name: "Retry loading" }).click();
    await expect(page.getByRole("heading", { name: "No projects yet" })).toBeVisible();
  });
}

test("a late 401 from the previous session does not remove a newer login", async ({ page, context }) => {
  await stubApi(context);
  let release!: () => void;
  const responseGate = new Promise<void>((resolve) => { release = resolve; });
  let entered!: () => void;
  const requestStarted = new Promise<void>((resolve) => { entered = resolve; });
  await context.route("**/api/v1/projects", async (route) => {
    entered();
    await responseGate;
    await route.fulfill({ status: 401, json: { detail: "Previous session expired" } });
  });
  await seed(page);
  await page.goto("/projects");
  await requestStarted;
  await page.evaluate(() => localStorage.setItem("rentwise_token", "synthetic-new-session"));
  release();
  await expect(page.locator("main").getByRole("alert")).toHaveText("Previous session expired");
  expect(await page.evaluate(() => localStorage.getItem("rentwise_token"))).toBe("synthetic-new-session");
  await expect(page).toHaveURL(/\/projects$/);
});
