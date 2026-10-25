import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { Compass } from "lucide-react";
import type { TourStep } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";
import { Dialog } from "@/components/ui/Dialog";
import { t } from "@/copy/t";
import { tour, useTour } from "@/state/tour";
import { ask } from "@/state/ask";
import { remToPx } from "@/lib/useContainerWidth";

const FIND_TIMEOUT_MS = 6000;
const FIND_INTERVAL_MS = 150;

/** Finds the spotlight target by data-tour (and data-tour-id when the step names one). */
export function findTourTarget(step: TourStep): HTMLElement | null {
  const kind = CSS.escape(step.target.kind);
  if (step.target.id) {
    const exact = document.querySelector<HTMLElement>(`[data-tour="${kind}"][data-tour-id="${CSS.escape(step.target.id)}"]`);
    if (exact) return exact;
  }
  return document.querySelector<HTMLElement>(`[data-tour="${kind}"]`);
}

function samePlace(route: string, pathname: string, search: string): boolean {
  const url = new URL(route, window.location.origin);
  if (url.pathname !== pathname) return false;
  const want = url.searchParams;
  const have = new URLSearchParams(search);
  for (const [k, v] of want) if (have.get(k) !== v) return false;
  return true;
}

/** The welcome card on first visit (localStorage keeper.tour.v1 absent). */
export function TourWelcome({ ready }: { ready: boolean }) {
  const s = useTour();
  return (
    <Dialog
      open={s.welcome && ready}
      onOpenChange={(o) => {
        if (!o) tour.explore();
      }}
      title={t("tour.welcome.title")}
      description={t("tour.welcome.body")}
      footer={
        <>
          <Button onClick={() => tour.explore()}>{t("tour.welcome.explore")}</Button>
          <Button variant="primary" icon={Compass} onClick={() => tour.start()} autoFocus>
            {t("tour.welcome.start")}
          </Button>
        </>
      }
    />
  );
}

/** Spotlight overlay: a dimmed page with a cut-out around the target and a popover with Back, Next, Skip. */
export function TourOverlay({ steps }: { steps: TourStep[] }) {
  const s = useTour();
  const navigate = useNavigate();
  const location = useLocation();
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [searching, setSearching] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef<HTMLElement | null>(null);
  const step = s.active ? steps[s.index] : undefined;

  // End of the tour: open Ask with three suggestions.
  useEffect(() => {
    if (s.finished) {
      ask.open(null, undefined, t("tour.end"));
      tour.clearFinished();
    }
  }, [s.finished]);

  // Go to the step's route.
  useEffect(() => {
    if (!step) return;
    if (!samePlace(step.route, location.pathname, location.search)) navigate(step.route);
  }, [step, navigate, location.pathname, location.search]);

  const measure = useCallback(() => {
    const el = targetRef.current;
    setRect(el && el.isConnected ? el.getBoundingClientRect() : null);
  }, []);

  // Find the target (it may render after data loads), then keep the cut-out in place.
  useEffect(() => {
    if (!step) return;
    targetRef.current = null;
    setRect(null);
    setSearching(true);
    const started = Date.now();
    const id = setInterval(() => {
      const el = findTourTarget(step);
      if (el) {
        targetRef.current = el;
        el.scrollIntoView({ block: "center", behavior: "auto" });
        measure();
        setSearching(false);
        clearInterval(id);
      } else if (Date.now() - started > FIND_TIMEOUT_MS) {
        setSearching(false);
        clearInterval(id);
      }
    }, FIND_INTERVAL_MS);
    return () => clearInterval(id);
  }, [step, location.pathname, measure]);

  const hasRect = rect !== null;
  useEffect(() => {
    if (!step) return;
    const on = () => measure();
    window.addEventListener("resize", on);
    window.addEventListener("scroll", on, true);
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(on) : null;
    if (targetRef.current) ro?.observe(targetRef.current);
    return () => {
      window.removeEventListener("resize", on);
      window.removeEventListener("scroll", on, true);
      ro?.disconnect();
    };
  }, [step, hasRect, measure]);

  useLayoutEffect(() => {
    if (step) cardRef.current?.focus();
  }, [step]);

  useEffect(() => {
    if (!step) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        tour.skip();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step]);

  if (!step) return null;
  const pad = remToPx(0.5);
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const below = rect ? vh - rect.bottom > rect.top : true;
  const cardStyle: React.CSSProperties = rect
    ? {
        left: Math.max(pad * 2, Math.min(rect.left, vw - Math.min(vw * 0.92, remToPx(26)) - pad * 2)),
        ...(below ? { top: Math.min(rect.bottom + pad * 2, vh - pad * 2) } : { bottom: Math.max(pad * 2, vh - rect.top + pad * 2) }),
      }
    : { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };

  return (
    <div className="fixed inset-0 z-[70]" role="presentation">
      {rect ? (
        <div
          aria-hidden
          className="pointer-events-none fixed rounded-md ring-2 ring-focus transition-all duration-(--dur-slow)"
          style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2, boxShadow: "0 0 0 200vmax var(--overlay)" }}
        />
      ) : (
        <div aria-hidden className="fixed inset-0 bg-overlay" />
      )}
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        tabIndex={-1}
        className="fixed w-[min(26rem,92vw)] rounded-lg border border-border bg-surface p-4 text-text shadow-dialog outline-none"
        style={cardStyle}
      >
        <p className="text-xs font-medium text-muted">{t("tour.stepOf", { index: s.index + 1, total: steps.length })}</p>
        <h2 id="tour-title" className="mt-1 text-lg font-semibold">
          {step.title}
        </h2>
        <Markdown source={step.body_md} className="mt-1.5 text-sm" />
        {searching ? <p className="mt-2 text-xs text-muted">{t("tour.finding")}</p> : null}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="ghost" onClick={() => tour.skip()}>
            {t("tour.skip")}
          </Button>
          <div className="ml-auto flex gap-2">
            <Button size="sm" disabled={s.index === 0} onClick={() => tour.back()}>
              {t("common.back")}
            </Button>
            <Button size="sm" variant="primary" onClick={() => tour.next(steps.length)}>
              {s.index + 1 >= steps.length ? t("tour.finish") : t("common.next")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
