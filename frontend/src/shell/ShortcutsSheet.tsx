import { Dialog } from "@/components/ui/Dialog";
import { Kbd } from "@/components/ui/Kbd";
import { t } from "@/copy/t";
import { NAV, SETTINGS_NAV } from "./nav";

export function ShortcutsSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const rows: Array<[string, string]> = [
    ...[...NAV, SETTINGS_NAV].map((n): [string, string] => [n.shortcut, t("shortcuts.goTo", { place: t(n.label) })]),
    ["/", t("shortcuts.slash")],
    ["?", t("shortcuts.help")],
    ["j k", t("shortcuts.findings")],
    ["n p", t("shortcuts.files")],
    ["w", t("shortcuts.wrap")],
    ["↑ ↓", t("shortcuts.rows")],
    ["Esc", t("shortcuts.esc")],
  ];
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={t("shortcuts.title")} description={t("shortcuts.body")}>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        {rows.map(([keys, what]) => (
          <div key={keys} className="contents">
            <dt>
              <Kbd keys={keys} />
            </dt>
            <dd>{what}</dd>
          </div>
        ))}
      </dl>
    </Dialog>
  );
}
