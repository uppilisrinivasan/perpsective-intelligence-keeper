import { useEffect, useRef, useState } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { onAuthRequired } from "@/api/client";
import { onJobTerminal } from "@/api/jobs";
import { useQueue } from "@/api/hooks/queue";
import { useSettings } from "@/api/hooks/settings";
import { usePeople, useProject, useProjectId, useProjects, useSession, useStatus, useTourSteps } from "@/api/hooks/system";
import { useActiveLens } from "@/screens/shared/lens";
import { AskDrawer } from "@/components/keeper/AskDrawer";
import { JobProgress, jobTitle } from "@/components/keeper/JobProgress";
import { TourOverlay, TourWelcome } from "@/components/keeper/TourOverlay";
import { Sheet } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { jobHref } from "@/lib/jobLinks";
import { errorMessage } from "@/lib/errors";
import { useGlobalShortcuts } from "@/lib/shortcuts";
import { MQ, useMediaQuery } from "@/lib/useMedia";
import { ask, useAsk, type AskContext } from "@/state/ask";
import { applyAppearance, usePrefs } from "@/state/prefs";
import { toViewerRole, useViewer, viewerStore } from "@/state/role";
import { toast } from "@/state/toasts";
import { tour, useTour } from "@/state/tour";
import { ApiError } from "@/api/errors";
import { BannerArea } from "./Banners";
import { BottomTabs, NavRail, type NavBadges } from "./NavRail";
import { ShortcutsSheet } from "./ShortcutsSheet";
import { Toaster } from "./Toaster";
import { Logo, TopBar } from "./TopBar";

/** The env var name for the model key, derived from the settings' secret names (never the value). */
export function useKeyEnvVar(): string | undefined {
  const settings = useSettings();
  const key = Object.keys(settings.data?.secrets ?? {}).find((k) => k.endsWith("_api_key"));
  return key?.toUpperCase();
}

function ServerDown({ onRetry, error }: { onRetry: () => void; error: unknown }) {
  const responded = error instanceof ApiError && error.status > 0;
  return (
    <main id="main" className="flex min-h-dvh flex-col items-center justify-center gap-4 px-(--gutter) text-center">
      <Logo />
      <h1 tabIndex={-1} data-page-title className="text-2xl font-semibold">
        {t("states.serverDown.title")}
      </h1>
      <p className="text-muted">{responded ? errorMessage(error) : t("states.serverDown.body")}</p>
      {error instanceof ApiError && error.requestId ? <p className="font-mono text-xs text-muted">{t("common.requestId", { id: error.requestId })}</p> : null}
      <Button variant="primary" onClick={onRetry}>
        {t("common.retry")}
      </Button>
    </main>
  );
}

function DataLoading({ jobId, error }: { jobId: string | null | undefined; error?: string | null }) {
  return (
    <div className="flex min-h-[60dvh] items-center justify-center px-(--gutter)">
      <div className="k-card w-full max-w-[32rem] space-y-3 p-6">
        <h1 tabIndex={-1} data-page-title className="text-xl font-semibold">
          {t("states.dataLoading.title")}
        </h1>
        <p className="text-sm text-muted">{t("states.dataLoading.body")}</p>
        {error ? <p className="text-sm text-danger-fg">{t("states.dataError", { error })}</p> : null}
        {jobId ? <JobProgress jobId={jobId} title={t("states.dataLoading.title")} /> : <Skeleton lines={3} />}
      </div>
    </div>
  );
}

function ShellSkeleton() {
  return (
    <div className="flex min-h-dvh">
      <div className="hidden w-(--rail-width) border-r border-border p-3 lg:block">
        <Skeleton lines={6} />
      </div>
      <div className="flex-1 p-(--gutter)">
        <Skeleton shape="block" className="mb-4 h-12" />
        <Skeleton lines={8} />
      </div>
    </div>
  );
}

/** Moves focus to the page h1 on route change and announces the title politely. */
function useRouteFocus(announce: (s: string) => void) {
  const location = useLocation();
  const first = useRef(true);
  useEffect(() => {
    let tries = 0;
    let raf = 0;
    const tick = () => {
      const h1 = document.querySelector<HTMLElement>("main [data-page-title]");
      if (h1) {
        const title = h1.textContent?.trim() ?? "";
        document.title = title ? t("shell.docTitle", { title }) : t("app.name");
        if (!first.current) {
          h1.focus({ preventScroll: false });
          announce(title);
        }
        first.current = false;
      } else if (tries++ < 40) {
        raf = window.setTimeout(tick, 100);
      }
    };
    tick();
    return () => window.clearTimeout(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);
}

export function AppShell() {
  const status = useStatus();
  const navigate = useNavigate();
  const location = useLocation();
  const pid = useProjectId();
  const projects = useProjects();
  const project = useProject(pid);
  const people = usePeople(pid);
  const settings = useSettings();
  const viewer = useViewer();
  const prefs = usePrefs();
  const askState = useAsk();
  const tourState = useTour();
  const envVar = useKeyEnvVar();
  const isLg = useMediaQuery(MQ.lg);
  const isRailWide = useMediaQuery(MQ.rail);
  const isSm = useMediaQuery(MQ.sm);
  const [navOpen, setNavOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const cloud = status.data?.auth_mode === "access_code";
  const session = useSession(Boolean(cloud));
  const loading = Boolean(status.data?.data.loading);
  const queue = useQueue(loading ? undefined : pid, "attention");
  const { overview } = useActiveLens(loading ? undefined : pid);
  const tourSteps = useTourSteps(Boolean(status.data) && !loading && (tourState.active || tourState.welcome));

  useRouteFocus(setAnnouncement);

  // If the tour can't load (or has no steps), end it instead of leaving an invisible overlay.
  useEffect(() => {
    if (!tourState.active) return;
    if (tourSteps.error || (tourSteps.data && tourSteps.data.steps.length === 0)) {
      toast({ tone: "warning", title: t("tour.unavailable") });
      tour.skip();
    }
  }, [tourState.active, tourSteps.error, tourSteps.data]);

  // Default "Viewing as" to the project's primary maintainer until the user picks someone.
  useEffect(() => {
    const pm = project.data?.primary_maintainer;
    if (!viewer.chosen && pm && viewer.personId !== pm.id) viewerStore.set({ personId: pm.id, role: toViewerRole(pm.role ?? "maintainer"), chosen: false });
  }, [project.data, viewer.chosen, viewer.personId]);

  // Theme, density and motion from the editable settings.
  useEffect(() => {
    const v = (key: string) => settings.data?.editable.find((e) => e.key === key)?.value as string | undefined;
    applyAppearance(v("theme"), v("reduced_motion"), v("density"));
  }, [settings.data]);

  // Toasts when a job finishes.
  useEffect(
    () =>
      onJobTerminal((s) => {
        const href = jobHref(s.kind, s.params, s.result);
        if (s.phase === "completed") toast({ tone: "success", title: t("toast.jobDone", { job: jobTitle(s.kind) }), href });
        else if (s.phase === "failed") toast({ tone: "danger", title: t("toast.jobFailed", { job: jobTitle(s.kind) }), body: s.error?.message, href });
      }),
    [],
  );

  useEffect(() => onAuthRequired(() => navigate("/signin")), [navigate]);

  useGlobalShortcuts({
    enabled: prefs.shortcuts,
    navigate,
    onHelp: () => setHelpOpen(true),
    onSlash: () => {
      const target = document.querySelector<HTMLElement>("[data-shortcut=search]") ?? document.querySelector<HTMLElement>("[data-shortcut=ask-input]");
      if (target) target.focus();
      else if (!askState.hidden) ask.open(currentContext(location.pathname));
    },
  });

  // Close the mobile nav on navigation.
  useEffect(() => setNavOpen(false), [location.pathname]);

  if (status.isLoading) return <ShellSkeleton />;
  if (status.error && !status.data) return <ServerDown onRetry={() => void status.refetch()} error={status.error} />;
  if (cloud && session.data && !session.data.signed_in) return <Navigate to="/signin" replace />;

  const s = status.data;
  const lens = overview.data;
  const badges: NavBadges = {
    queue: queue.data?.summary.need_count || undefined,
    lensDot: Boolean(lens && (lens.unconsumed_feedback ?? 0) > 0 && (lens.unconsumed_feedback ?? 0) >= (lens.update_min_events ?? 1)),
  };
  const collapsed = prefs.railCollapsed || !isRailWide;

  return (
    <div className="flex min-h-dvh bg-bg text-text">
      <a href="#main" className="sr-only z-[80] rounded-md bg-surface px-3 py-2 focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:shadow-pop">
        {t("nav.skip")}
      </a>
      {isLg ? (
        <aside className={cx("sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-surface lg:flex", collapsed ? "w-(--rail-width-collapsed)" : "w-(--rail-width)")} aria-label={t("shell.sidebar")}>
          <div className={cx("flex min-h-(--topbar-height) items-center border-b border-border", collapsed ? "justify-center" : "px-3")}>
            {collapsed ? (
              <Link to="/queue" aria-label={t("shell.home")} className="flex size-8 items-center justify-center rounded-full bg-edge-solid">
                <span className="size-3 rounded-full bg-surface" aria-hidden />
              </Link>
            ) : (
              <Logo />
            )}
          </div>
          <div className="min-h-0 flex-1">
            <NavRail badges={badges} forceExpanded={false} />
          </div>
        </aside>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          status={s}
          projects={projects.data?.items ?? []}
          people={people.data?.items ?? []}
          pid={pid}
          showMenu={!isLg}
          onMenu={() => setNavOpen(true)}
          askHidden={askState.hidden}
          onAsk={() => ask.open(currentContext(location.pathname, location.search))}
          envVar={envVar}
        />
        {s ? <BannerArea status={s} envVar={envVar} /> : null}
        <main id="main" tabIndex={-1} className={cx("@container/main min-w-0 flex-1 outline-none", !isSm && "pb-16")}>
          {loading ? <DataLoading jobId={s?.data.load_job_id} error={s?.data.error} /> : <Outlet />}
        </main>
      </div>
      {!isLg ? (
        <Sheet open={navOpen} onOpenChange={setNavOpen} title={t("nav.menu")} side="left" width="nav">
          <NavRail badges={badges} forceExpanded onNavigate={() => setNavOpen(false)} />
        </Sheet>
      ) : null}
      {!isSm ? <BottomTabs badges={badges} onMore={() => setNavOpen(true)} /> : null}
      <AskDrawer />
      {s && !loading ? <TourWelcome ready /> : null}
      {tourSteps.data?.steps.length ? <TourOverlay steps={tourSteps.data.steps} /> : null}
      <ShortcutsSheet open={helpOpen} onOpenChange={setHelpOpen} />
      <Toaster />
      <div className="sr-only" aria-live="polite" role="status">
        {announcement}
      </div>
    </div>
  );
}

/** The Ask context for the current route (the drawer's "Ask about this"). */
export function currentContext(pathname: string, search = ""): AskContext | null {
  const params = new URLSearchParams(search);
  const pr = /^\/pr\/(\d+)/.exec(pathname);
  if (pr) return { screen: "pr", number: Number(pr[1]) };
  if (pathname.startsWith("/queue")) return { screen: "queue" };
  if (pathname.startsWith("/lens")) return { screen: "lens", item_id: params.get("item") ?? undefined };
  if (pathname.startsWith("/proof")) return { screen: "proof", run_id: params.get("run") ?? undefined };
  if (pathname.startsWith("/practice")) return { screen: "practice" };
  return null;
}

