/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import { existsSync, readFileSync } from "node:fs";

/** Documented defaults from the repository-root example env file, used only for keys missing elsewhere. */
function exampleDefaults(): Record<string, string> {
  const file = fileURLToPath(new URL("../.env.example", import.meta.url));
  if (!existsSync(file)) return {};
  const out: Record<string, string> = {};
  for (const m of readFileSync(file, "utf8").matchAll(/^([A-Z0-9_]+)=([^#\n]*)/gm)) {
    const value = m[2]?.trim();
    if (m[1] && value) out[m[1]] = value;
  }
  return out;
}

// Ports come from the repository-root .env (one level up) via loadEnv, falling back to the process
// environment, then to the documented defaults. No port is hardcoded here.
export default defineConfig(({ mode }) => {
  const env: Record<string, string | undefined> = { ...exampleDefaults(), ...process.env, ...loadEnv(mode, "..", "") };
  const appPort = env.APP_PORT;
  const devPort = env.FRONTEND_DEV_PORT ? Number(env.FRONTEND_DEV_PORT) : undefined;
  const host = env.APP_HOST && env.APP_HOST !== "0.0.0.0" ? env.APP_HOST : "127.0.0.1";
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
    server: {
      // Bind the same loopback address the backend uses, so the URL run.sh opens always resolves.
      host,
      port: devPort,
      strictPort: devPort !== undefined,
      proxy: appPort
        ? {
            "/api": {
              target: `http://${host}:${appPort}`,
              changeOrigin: false,
              configure: (proxy) => {
                proxy.on("proxyRes", (proxyRes) => {
                  // Server-sent events must not be buffered by the proxy.
                  proxyRes.headers["x-accel-buffering"] = "no";
                  if (String(proxyRes.headers["content-type"] ?? "").includes("text/event-stream")) {
                    proxyRes.headers["cache-control"] = "no-cache, no-transform";
                  }
                });
              },
            },
          }
        : undefined,
    },
    build: { outDir: "dist", sourcemap: true, chunkSizeWarningLimit: 900 },
    test: {
      environment: "jsdom",
      globals: false,
      setupFiles: ["./vitest.setup.ts"],
      include: ["tests/unit/**/*.test.{ts,tsx}"],
      css: false,
    },
  };
});
