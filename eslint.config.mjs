// Shared script fragments are assembled by web/build.sh. Cross-file names are intentional.
export default [{
  ignores: ["web/keystep-interactive-manual.html", "web/kscon-install.html", "out/**", "firmware/**", ".venv/**",
    // These are async function bodies evaluated by cdp.mjs, not standalone scripts.
    "web/tests/ccmap.js", "web/tests/functional.js", "web/tests/fwpatch.js", "web/tests/tour-walk.js"],
}, {
  files: ["**/*.js", "**/*.mjs"],
  languageOptions: { ecmaVersion: "latest", sourceType: "module" },
  rules: {
    "constructor-super": "error",
    "no-cond-assign": ["warn", "except-parens"],
    "no-constant-binary-expression": "error",
    "no-dupe-args": "error",
    "no-dupe-class-members": "error",
    "no-dupe-else-if": "error",
    "no-dupe-keys": "error",
    "no-duplicate-case": "error",
    "no-ex-assign": "error",
    "no-func-assign": "error",
    "no-import-assign": "error",
    "no-obj-calls": "error",
    "no-promise-executor-return": "warn",
    "no-setter-return": "error",
    "no-unexpected-multiline": "error",
    "no-unreachable": "error",
    "no-unsafe-finally": "error",
    "no-unsafe-negation": "error",
    "use-isnan": "error",
    "valid-typeof": "error",
  },
}];
