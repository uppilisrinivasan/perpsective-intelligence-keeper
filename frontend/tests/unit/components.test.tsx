import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { LaneBadge } from "@/components/keeper/Lane";
import { QueueRow, rowAccessibleName } from "@/components/keeper/QueueRow";
import { FindingCard } from "@/components/keeper/FindingCard";
import { CompareBars } from "@/components/keeper/Metrics";
import { t } from "@/copy/t";
import { renderUi } from "./render";
import { finding, provenance, queueRow } from "./fixtures/factories";

describe("LaneBadge", () => {
  it("shows the icon and label, never colour alone", () => {
    const { container } = renderUi(<LaneBadge lane="edge" />);
    expect(screen.getByText(t("lane.edge.label"))).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
    expect(container.querySelector("[data-lane=edge]")).not.toBeNull();
  });

  it("keeps the label for screen readers when hidden visually", () => {
    renderUi(<LaneBadge lane="unknown" showLabel={false} />);
    expect(screen.getByText(t("lane.unknown.label"))).toHaveClass("sr-only");
  });

  it("falls back to 'Not sorted yet' for unknown values", () => {
    renderUi(<LaneBadge lane="something-new" />);
    expect(screen.getByText(t("lane.unsorted.label"))).toBeInTheDocument();
  });
});

describe("QueueRow", () => {
  it("is a link with the full accessible name", () => {
    const row = queueRow();
    renderUi(
      <ul>
        <QueueRow row={row} href="/pr/9001" />
      </ul>,
    );
    const link = screen.getByRole("link", { name: rowAccessibleName(row) });
    expect(link).toHaveAttribute("href", "/pr/9001");
    expect(rowAccessibleName(row)).toContain(t("lane.edge.label").toLowerCase());
    expect(screen.getByText(t("queue.row.firstTime"))).toBeInTheDocument();
    expect(screen.getByText(t("queue.row.findings", { n: 2 }))).toBeInTheDocument();
  });

  it("offers the hand-off on unknown rows", () => {
    const onHandoff = vi.fn();
    const row = queueRow({ lane: "unknown", handoff: { person_id: "per_b", display_name: "Reviewer B" } });
    renderUi(
      <ul>
        <QueueRow row={row} href="/pr/9001" onHandoff={onHandoff} />
      </ul>,
    );
    fireEvent.click(screen.getByRole("button", { name: t("queue.row.handTo", { name: "Reviewer B" }) }));
    expect(onHandoff).toHaveBeenCalledWith(row);
  });

  it("shows 'Not sorted yet' without an analysis", () => {
    renderUi(
      <ul>
        <QueueRow row={queueRow({ analysis_id: null })} href="/pr/9001" maintainer="Maintainer A" />
      </ul>,
    );
    expect(screen.getAllByText(t("lane.unsorted.label")).length).toBeGreaterThan(0);
    expect(screen.getByText(t("lane.unsorted.meaning", { maintainer: "Maintainer A" }))).toBeInTheDocument();
  });

  it("marks saved results on the lane chip", () => {
    const { container } = renderUi(
      <ul>
        <QueueRow row={queueRow({ provenance: provenance({ origin: "snapshot" }) })} href="/pr/9001" />
      </ul>,
    );
    expect(container.querySelectorAll("[data-lane=edge] svg").length).toBe(2);
  });

  it("selects instead of navigating on pointer click when a preview pane is shown", () => {
    const onSelect = vi.fn();
    renderUi(
      <ul>
        <QueueRow row={queueRow()} href="/pr/9001" onSelect={onSelect} />
      </ul>,
    );
    fireEvent.click(screen.getByRole("link"), { detail: 1 });
    expect(onSelect).toHaveBeenCalledWith(9001);
  });
});

describe("FindingCard", () => {
  it("renders the title, meta, evidence and confidence word", () => {
    renderUi(<FindingCard finding={finding()} maintainer="Maintainer A" />);
    expect(screen.getByRole("heading", { name: finding().title })).toBeInTheDocument();
    expect(screen.getByText(t("confidence.high"))).toBeInTheDocument();
    expect(screen.getByText("Safe include paths")).toBeInTheDocument();
    expect(screen.getByText(t("format.pathLine", { path: "pkg/loaders/yaml.py", line: 44 }))).toBeInTheDocument();
  });

  it("sends feedback and offers Undo", () => {
    const onFeedback = vi.fn();
    const { rerender } = renderUi(<FindingCard finding={finding()} maintainer="M" onFeedback={onFeedback} />);
    fireEvent.click(screen.getByRole("button", { name: t("finding.action.accept") }));
    expect(onFeedback).toHaveBeenCalledWith({ state: "accepted" });
    rerender(<FindingCard finding={finding({ user_state: "accepted" })} maintainer="M" onFeedback={onFeedback} />);
    expect(screen.getByText(t("finding.state.accepted"))).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: t("common.undo") }));
    expect(onFeedback).toHaveBeenLastCalledWith({ state: "open" });
  });

  it("shows Fix and test only when fixable and allowed", () => {
    const onFix = vi.fn();
    const { rerender } = renderUi(<FindingCard finding={finding()} maintainer="M" onFeedback={() => undefined} onFix={onFix} canFix />);
    fireEvent.click(screen.getByRole("button", { name: t("finding.action.fix") }));
    expect(onFix).toHaveBeenCalled();
    rerender(<FindingCard finding={finding({ fixable: false })} maintainer="M" onFeedback={() => undefined} onFix={onFix} canFix />);
    expect(screen.queryByRole("button", { name: t("finding.action.fix") })).toBeNull();
  });

  it("offers Good catch only for blind spots", () => {
    const { rerender } = renderUi(<FindingCard finding={finding()} maintainer="M" onFeedback={() => undefined} />);
    expect(screen.queryByRole("button", { name: t("finding.action.goodCatch") })).toBeNull();
    rerender(<FindingCard finding={finding({ lane: "blind_spot" })} maintainer="M" onFeedback={() => undefined} />);
    expect(screen.getByRole("button", { name: t("finding.action.goodCatch") })).toBeInTheDocument();
  });

  it("disables actions with a reason for other roles", () => {
    renderUi(<FindingCard finding={finding()} maintainer="M" onFeedback={() => undefined} disabledReason={t("common.onlyMaintainer")} />);
    expect(screen.getByRole("button", { name: t("finding.action.accept") })).toBeDisabled();
  });
});

describe("CompareBars", () => {
  it("shows each system's value, interval and the paired difference", () => {
    renderUi(
      <CompareBars
        title="Recall"
        rows={[
          { key: "k", label: "System K", metric: { value: 0.64, low: 0.55, high: 0.72, n: 38 }, tone: "primary" },
          { key: "b", label: "System B", metric: { value: 0.33, low: 0.25, high: 0.41, n: 38 }, tone: "baseline" },
        ]}
        difference={{ value: 0.31, low: 0.22, high: 0.4 }}
      />,
    );
    expect(screen.getByText("64%")).toBeInTheDocument();
    expect(screen.getByText("(55–72)")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: t("metric.aria", { label: "System B", value: "33%", interval: "(25–41)" }) })).toBeInTheDocument();
    expect(screen.getByText(t("proof.difference", { value: "+31 points", interval: "(22–40)" }))).toBeInTheDocument();
    expect(screen.getByText(t("proof.aboveZero"))).toBeInTheDocument();
  });

  it("flags a small sample", () => {
    renderUi(<CompareBars title="R" rows={[{ key: "k", label: "K", metric: { value: 0.5, low: 0.2, high: 0.8, n: 6 }, tone: "primary" }]} />);
    expect(screen.getByText(t("format.smallSample"))).toBeInTheDocument();
  });
});
