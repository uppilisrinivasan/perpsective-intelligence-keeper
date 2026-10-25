import { QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "./errors";
import { notifyAuthRequired } from "./client";

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError(error) {
      if (error instanceof ApiError && error.code === "auth_required") notifyAuthRequired();
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry(failureCount, error) {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        if (error instanceof ApiError && error.code === "no_api_key") return false;
        return failureCount < 2;
      },
    },
    mutations: { retry: false },
  },
});
