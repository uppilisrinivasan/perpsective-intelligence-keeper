import { useState } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { LogIn } from "lucide-react";
import { api, call } from "@/api/client";
import { InlineError } from "@/components/keeper/States";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { t } from "@/copy/t";
import { Logo } from "@/shell/TopBar";

/** Cloud mode only: a single access-code field. */
export default function SignInScreen() {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const navigate = useNavigate();
  const qc = useQueryClient();
  return (
    <main id="main" className="flex min-h-dvh items-center justify-center bg-bg px-(--gutter)">
      <form
        className="k-card w-full max-w-[26rem] space-y-4 p-6"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await call(api.POST("/api/v1/auth/session", { body: { access_code: code } }));
            await qc.invalidateQueries();
            navigate("/queue", { replace: true });
          } catch (err) {
            setError(err);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Logo />
        <h1 tabIndex={-1} data-page-title className="text-xl font-semibold">
          {t("signin.title")}
        </h1>
        <p className="text-sm text-muted">{t("signin.body")}</p>
        <TextField label={t("signin.code")} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" required autoFocus />
        {error ? <InlineError error={error} /> : null}
        <Button type="submit" variant="primary" icon={LogIn} loading={busy} className="w-full">
          {t("signin.submit")}
        </Button>
      </form>
    </main>
  );
}
