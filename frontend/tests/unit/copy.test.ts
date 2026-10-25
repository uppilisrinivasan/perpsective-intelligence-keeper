import { describe, expect, it } from "vitest";
import { IntlMessageFormat } from "intl-messageformat";
import messages from "@/copy/en.json";
import { t, tDynamic, hasCopy } from "@/copy/t";

describe("copy formatter", () => {
  it("formats plurals with ICU rules", () => {
    expect(t("queue.answer.some", { need: 1, total: 12, minutes: 20, budget: 120 })).toBe("1 of 12 pull requests needs you · about 20 min of your 120-min week");
    expect(t("queue.answer.some", { need: 4, total: 12, minutes: 55, budget: 120 })).toBe("4 of 12 pull requests need you · about 55 min of your 120-min week");
  });

  it("handles =0 plural branches and nested arguments", () => {
    expect(t("practice.item.notesCount", { n: 0 })).toBe("No notes yet");
    expect(t("practice.item.notesCount", { n: 1 })).toBe("1 note");
    expect(t("practice.item.notesCount", { n: 3 })).toBe("3 notes");
  });

  it("keeps apostrophes in possessives", () => {
    expect(t("lens.title", { name: "Ada" })).toBe("Ada's lens");
  });

  it("renders a missing variable as empty instead of throwing", () => {
    expect(t("lens.title")).toBe("'s lens");
  });

  it("falls back for unknown dynamic keys", () => {
    expect(tDynamic("job.kind.nope", undefined, "job.kind.generic")).toBe(t("job.kind.generic"));
    expect(tDynamic("does.not.exist")).toBe("");
    expect(hasCopy("lane.edge.label")).toBe(true);
  });

  it("every string in en.json is valid ICU MessageFormat", () => {
    for (const [key, value] of Object.entries(messages)) {
      expect(() => new IntlMessageFormat(value as string, "en", undefined, { ignoreTag: true }), key).not.toThrow();
    }
  });

  it("uses the fixed lane vocabulary", () => {
    expect(t("lane.edge.label")).toBe("Needs your eye");
    expect(t("lane.blind_spot.label")).toBe("Worth a second look");
    expect(t("lane.shared.label")).toBe("Handled for you");
    expect(t("lane.unknown.label")).toBe("Needs another reviewer");
    expect(t("lane.baseline_only.label")).toBe("Other model notes");
  });
});
