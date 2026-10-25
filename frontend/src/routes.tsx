import { createBrowserRouter, Navigate, useRouteError, type RouteObject } from "react-router";
import { AppShell } from "@/shell/AppShell";
import { PageError, EmptyState } from "@/components/keeper/States";
import { t } from "@/copy/t";
import { Link } from "react-router";
import { buttonClass } from "@/components/ui/Button";

function RouteError() {
  const error = useRouteError();
  return <PageError error={error} onRetry={() => window.location.reload()} />;
}

function NotFound() {
  return (
    <div className="k-page">
      <h1 tabIndex={-1} data-page-title className="sr-only">
        {t("states.notFound.title")}
      </h1>
      <EmptyState
        title={t("states.notFound.title")}
        body={t("states.notFound.body")}
        action={
          <Link to="/queue" className={buttonClass("primary")}>
            {t("states.goToQueue")}
          </Link>
        }
      />
    </div>
  );
}

const screen = (load: () => Promise<{ default: React.ComponentType }>) => ({
  lazy: async () => ({ Component: (await load()).default }),
});

/** Routes and deep links (docs/05-api/04-frontend-integration.md §5). */
export const routes: RouteObject[] = [
  { path: "/signin", ...screen(() => import("@/screens/signin")), errorElement: <RouteError /> },
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Navigate to="/queue" replace /> },
      { path: "queue", ...screen(() => import("@/screens/queue")), errorElement: <RouteError /> },
      { path: "pr/:number", ...screen(() => import("@/screens/pull")), errorElement: <RouteError /> },
      { path: "pr/:number/fix/:fixId", ...screen(() => import("@/screens/pull")), errorElement: <RouteError /> },
      { path: "ask", ...screen(() => import("@/screens/ask")), errorElement: <RouteError /> },
      { path: "ask/:threadId", ...screen(() => import("@/screens/ask")), errorElement: <RouteError /> },
      { path: "lens", ...screen(() => import("@/screens/lens")), errorElement: <RouteError /> },
      { path: "proof", ...screen(() => import("@/screens/proof")), errorElement: <RouteError /> },
      { path: "practice", ...screen(() => import("@/screens/practice")), errorElement: <RouteError /> },
      { path: "practice/:sessionId/:index", ...screen(() => import("@/screens/practice/Item")), errorElement: <RouteError /> },
      { path: "settings", ...screen(() => import("@/screens/settings")), errorElement: <RouteError /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export function createRouter() {
  return createBrowserRouter(routes);
}
