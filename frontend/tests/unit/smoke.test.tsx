/**
 * Route smoke test: every screen renders through the real router, shell and providers against a stubbed fetch
 * (test-only fixtures), with one h1 per page and the no-key/simulated labelling visible.
 */
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router";
import { routes } from "@/routes";
import { queryClient } from "@/api/queryClient";
import { ConfirmProvider } from "@/api/hooks/confirm";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { TOUR_STORAGE_KEY, tourStore } from "@/state/tour";
import { t } from "@/copy/t";
import { fixtures } from "./fixtures/api";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

beforeAll(() => {
  window.localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ outcome: "skipped" }));
  tourStore.set({ active: false, index: 0, welcome: false, finished: false });
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  window.matchMedia = ((q: string) => ({ matches: q.includes("64rem"), media: q, addEventListener() {}, removeEventListener() {}, onchange: null, addListener() {}, removeListener() {}, dispatchEvent: () => false })) as unknown as typeof window.matchMedia;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, "http://localhost");
      const body = fixtures[url.pathname];
      if (body === undefined) return json({ error: { code: "not_found", message: "", details: {}, request_id: "req_t" } }, 404);
      return json(body);
    }),
  );
});

afterAll(() => {
  vi.unstubAllGlobals();
});

async function visit(path: string) {
  queryClient.clear();
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <ConfirmProvider>
          <RouterProvider router={router} />
        </ConfirmProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(document.querySelectorAll("main h1").length).toBeGreaterThan(0), { timeout: 4000 });
  await new Promise((r) => setTimeout(r, 50));
}

describe("route smoke", () => {
  it("Queue: answer header, rows, and the simulated no-key banner", async () => {
    await visit("/queue");
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(t("queue.answer.some", { need: 2, total: 2, minutes: 35, budget: 120 })));
    expect(document.querySelectorAll("main h1")).toHaveLength(1);
    expect(screen.getAllByText(t("banner.noKeySimulated", { date: "", provider: "Provider P" }).slice(0, 40), { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: t("queue.row.handTo", { name: "rev b" }) })).toBeInTheDocument();
  });

  it("Pull request: title, findings and diff", async () => {
    await visit("/pr/9001");
    await waitFor(() => expect(screen.getAllByText("Include paths can escape the base directory").length).toBeGreaterThan(0));
    expect(document.querySelectorAll("main h1")).toHaveLength(1);
    expect(screen.getAllByText("pkg/loaders/yaml.py").length).toBeGreaterThan(0);
  });

  it("Pull request compare view", async () => {
    await visit("/pr/9001?view=compare");
    await waitFor(() => expect(screen.getAllByText(t("compare.col.baseline")).length).toBeGreaterThan(0));
    expect(screen.getByText("Path escape")).toBeInTheDocument();
  });

  it("Lens card with item chips", async () => {
    await visit("/lens");
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(t("lens.title", { name: "maint a" })));
    await waitFor(() => expect(screen.getAllByText("Safe include paths").length).toBeGreaterThan(0));
  });

  it("Lens map tab", async () => {
    await visit("/lens?tab=map");
    await waitFor(() => expect(screen.getByText(t("edge.multiplier", { x: "3.4" }))).toBeInTheDocument());
  });

  it("Proof verdict and bars", async () => {
    await visit("/proof");
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(t("proof.verdict.pass", { name: "maint a", n: 10 })));
    expect(screen.getAllByText("60%").length).toBeGreaterThan(0);
  });

  it("Practice landing", async () => {
    await visit("/practice");
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(t("practice.title", { name: "maint a" })));
  });

  it("Settings", async () => {
    await visit("/settings");
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t("settings.title")));
    expect(screen.getByText("Judge Model")).toBeInTheDocument();
  });

  it("Ask in no-key mode lists saved examples", async () => {
    await visit("/ask");
    await waitFor(() => expect(screen.getAllByText("What needs me today?").length).toBeGreaterThan(0));
  });

  it("Ask saved example renders a citation chip", async () => {
    await visit("/ask/example:ex1");
    await waitFor(() => expect(screen.getByText(t("ask.savedSimulated"))).toBeInTheDocument());
    expect(screen.getAllByText(t("format.prNumber", { n: 9001 })).length).toBeGreaterThan(0);
  });

  it("unknown routes show the not-found state", async () => {
    await visit("/nowhere");
    expect(screen.getAllByText(t("states.notFound.title")).length).toBeGreaterThan(0);
  });
});
