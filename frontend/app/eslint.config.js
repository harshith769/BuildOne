import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "src/api/schema.d.ts", "playwright-report", "test-results"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.strict],
    languageOptions: { ecmaVersion: 2023, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // API data must come through the generated client (.claude/rules/frontend.md).
      "no-restricted-globals": ["error", { name: "fetch", message: "Use the generated client in src/api/client.ts." }],
    },
  },
  {
    files: ["src/api/client.ts", "e2e/**", "*.config.ts"],
    rules: { "no-restricted-globals": "off" },
  },
);
