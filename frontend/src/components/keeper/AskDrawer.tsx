import { useNavigate } from "react-router";
import { ExternalLink } from "lucide-react";
import { Sheet } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { AskChat, contextLabel } from "@/screens/ask/AskChat";
import { ask, contextKey, useAsk } from "@/state/ask";
import { t } from "@/copy/t";

/** The Ask chat as a right-side drawer (a full-screen sheet below lg), with the current context attached. */
export function AskDrawer() {
  const s = useAsk();
  const navigate = useNavigate();
  const key = contextKey(s.context);
  const tid = s.threads[key];
  const label = contextLabel(s.context);
  return (
    <Sheet
      open={s.open && !s.hidden}
      onOpenChange={(o) => (o ? undefined : ask.close())}
      title={label ? t("ask.drawer.titleAbout", { label }) : t("ask.drawer.title")}
      headerExtra={
        tid ? (
          <Button
            size="sm"
            variant="ghost"
            icon={ExternalLink}
            onClick={() => {
              ask.close();
              navigate(`/ask/${tid}`);
            }}
          >
            {t("ask.drawer.openInAsk")}
          </Button>
        ) : null
      }
    >
      <div className="flex h-full flex-col px-4">
        {s.intro ? <p className="mt-3 rounded-md bg-info-bg p-3 text-sm text-info-fg">{s.intro}</p> : null}
        <div className="min-h-0 flex-1">
          <AskChat
            key={key}
            compact
            threadId={tid}
            context={s.context}
            onContextChange={(c) => ask.setContext(c)}
            onThreadCreated={(id) => ask.setThread(key, id)}
            prefill={s.prefill}
            autoFocus
          />
        </div>
      </div>
    </Sheet>
  );
}
