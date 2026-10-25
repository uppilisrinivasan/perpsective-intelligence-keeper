import { ChevronDown } from "lucide-react";
import type { PersonSummary } from "@/api/types";
import { Menu } from "@/components/ui/Menu";
import { PersonAvatar } from "@/components/keeper/PersonAvatar";
import { chooseViewer, useViewer } from "@/state/role";
import { t, tDynamic } from "@/copy/t";
import { personName } from "@/lib/format";

export function roleWord(role: string): string {
  return tDynamic(`people.role.${role}`) || role.replace(/_/g, " ");
}

/** "Viewing as: {name} ({role})" — changes X-Keeper-Role, which lens is shown and the default learner. */
export function RolePicker({ people }: { people: PersonSummary[] }) {
  const viewer = useViewer();
  const current = people.find((p) => p.id === viewer.personId);
  const label = current ? t("people.withRole", { name: personName(current), role: roleWord(current.role) }) : t("people.judge");
  return (
    <Menu
      label={t("role.menu")}
      trigger={
        <button type="button" className="inline-flex min-w-0 items-center gap-1.5 rounded-md border border-border px-2 py-1 text-sm hover:bg-surface-2" aria-label={t("role.aria", { label })}>
          {current ? <PersonAvatar personId={current.id} size="sm" /> : null}
          <span className="hidden text-muted xl:inline">{t("role.viewingAs")}</span>
          <span className="max-w-[12rem] truncate font-medium max-md:sr-only">{label}</span>
          <ChevronDown className="size-4 text-muted" aria-hidden />
        </button>
      }
      items={[
        ...people.map((p) => ({
          key: p.id,
          label: t("people.withRole", { name: personName(p), role: roleWord(p.role) }),
          checked: viewer.personId === p.id,
          onSelect: () => chooseViewer(p.id, p.role),
        })),
        "separator" as const,
        { key: "judge", label: t("people.judge"), checked: viewer.personId === null, onSelect: () => chooseViewer(null, "judge") },
      ]}
    />
  );
}
