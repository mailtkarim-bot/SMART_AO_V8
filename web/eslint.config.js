import js from "@eslint/js";
import babelParser from "@babel/eslint-parser";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  js.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: babelParser,
      parserOptions: {
        requireConfigFile: false,
        babelOptions: {
          presets: ["@babel/preset-typescript", "@babel/preset-react"],
        },
      },
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs["recommended-latest"].rules,
      "no-undef": "off",
      "no-unused-vars": "off",
      "react-hooks/set-state-in-effect": "off",
    },
  },
];
