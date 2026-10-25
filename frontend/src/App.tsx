import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { useState } from "react";
import { queryClient } from "@/api/queryClient";
import { ConfirmProvider } from "@/api/hooks/confirm";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { createRouter } from "./routes";

export function App() {
  const [router] = useState(createRouter);
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <ConfirmProvider>
          <RouterProvider router={router} />
        </ConfirmProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
