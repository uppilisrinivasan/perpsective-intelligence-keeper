import { Link, useSearchParams } from "react-router";
import { ChevronDown, Compass, Menu as MenuIcon, MessageSquare } from "lucide-react";
import type { PersonSummary, ProjectSummary, Status } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { Menu } from "@/components/ui/Menu";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { tour } from "@/state/tour";
import { ActivityButton } from "./Activity";
import { ModeBadge } from "./ModeBadge";
import { RolePicker } from "./RolePicker";

export function Logo() {
  return (
    <Link to="/queue" className="flex items-center gap-2 rounded-md px-1 font-semibold" aria-label={t("shell.home")}>
      <span className="relative flex size-6 items-center justify-center rounded-full bg-edge-solid" aria-hidden>
        <span className="size-2.5 rounded-full bg-surface" />
      </span>
      <span className="text-base">{t("app.name")}</span>
    </Link>
  );
}

function ProjectLabel({ projects, pid }: { projects: ProjectSummary[]; pid: string | undefined }) {
  const [params, setParams] = useSearchParams();
  const current = projects.find((p) => p.id === pid);
  if (!current) return null;
  const name = t("shell.project", { owner: current.owner, repo: current.repo });
  const label = <span className="truncate font-mono text-sm">{name}</span>;
  return (
    <div className="flex min-w-0 items-center gap-2">
      {projects.length > 1 ? (
        <Menu
          align="start"
          label={t("shell.switchProject")}
          trigger={
            <button type="button" className="inline-flex min-w-0 items-center gap-1 rounded-md px-1.5 py-1 hover:bg-surface-2">
              {label}
              <ChevronDown className="size-4 text-muted" aria-hidden />
            </button>
          }
          items={projects.map((p) => ({
            key: p.id,
            label: t("shell.project", { owner: p.owner, repo: p.repo }),
            checked: p.id === pid,
            onSelect: () => {
              const next = new URLSearchParams(params);
              next.set("project", p.id);
              setParams(next);
            },
          }))}
        />
      ) : (
        <span className="min-w-0 px-1.5">{label}</span>
      )}
      {current.fictional ? (
        <Tooltip content={t("shell.demoWorldTip")}>
          <span tabIndex={0}>
            <Badge tone="outline">{t("shell.demoWorld")}</Badge>
          </span>
        </Tooltip>
      ) : null}
    </div>
  );
}

export function TopBar({ status, projects, people, pid, onMenu, showMenu, askHidden, onAsk, envVar }: {
  status: Status | undefined;
  projects: ProjectSummary[];
  people: PersonSummary[];
  pid: string | undefined;
  onMenu: () => void;
  showMenu: boolean;
  askHidden: boolean;
  onAsk: () => void;
  envVar?: string;
}) {
  return (
    <header className="sticky top-0 z-20 flex min-h-(--topbar-height) flex-wrap items-center gap-x-2 gap-y-1 border-b border-border bg-surface/95 px-(--gutter) py-1.5 backdrop-blur">
      {showMenu ? <IconButton icon={MenuIcon} label={t("nav.menu")} onClick={onMenu} /> : null}
      {showMenu ? <Logo /> : null}
      <ProjectLabel projects={projects} pid={pid} />
      <div className="flex-1" />
      <div className="flex items-center gap-1.5">
        {status ? <ModeBadge status={status} envVar={envVar} /> : null}
        {people.length ? <RolePicker people={people} /> : null}
        <ActivityButton />
        <Tooltip content={t("tour.restart")}>
          <Button size="sm" variant="ghost" icon={Compass} onClick={() => tour.start()} className="max-md:px-2" aria-label={t("tour.restart")}>
            <span className="max-md:sr-only">{t("tour.button")}</span>
          </Button>
        </Tooltip>
        <Tooltip content={askHidden ? t("shell.askHidden") : undefined}>
          <span>
            <Button size="sm" variant="secondary" icon={MessageSquare} onClick={onAsk} disabled={askHidden} data-tour="ask_button">
              <span className="max-sm:sr-only">{t("nav.ask")}</span>
            </Button>
          </span>
        </Tooltip>
      </div>
    </header>
  );
}
