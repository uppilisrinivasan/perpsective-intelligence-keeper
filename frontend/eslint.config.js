import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import keeper from "./eslint-rules/keeper.js";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/api/schema.d.ts", "coverage", "playwright-report"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2023, globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks, keeper },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-syntax": [
        "error",
        { selector: "Literal[value=/nvidia\\//i]", message: "Model IDs come from the API, never from code." },
        { selector: "Literal[value=/Nemotron/]", message: "Model names come from the API, never from code." },
      ],
    },
  },
  {
    files: ["src/**/*.tsx"],
    rules: { "keeper/no-literal-copy": "error", "keeper/no-fixed-px": "error" },
  },
  {
    files: ["eslint-rules/**/*.js", "scripts/**/*.mjs"],
    languageOptions: { globals: { ...globals.node } },
  },
);
