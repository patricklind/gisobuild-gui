// ESLint config for the two plain (non-module) <script> files templates/index.html
// loads together: app.js first, then manual-packages.js. Top-level `let`/`const`
// declarations in a classic script are not window properties, but they DO share
// one lexical scope across every classic <script> tag on the same page - so
// each file can reference a handful of the other's top-level bindings without
// either declaring or importing them. The `overrides` below tell each file's
// own lint pass about exactly the names it borrows from the other, without
// telling a file about names it already declares itself (which would make
// no-redeclare treat its own real declaration as a conflicting redeclaration).
module.exports = {
  env: { browser: true, es2021: true },
  parserOptions: { ecmaVersion: 2021, sourceType: "script" },
  rules: {
    "no-undef": "error",
    "no-unused-vars": "error",
    "no-unreachable": "error",
    "no-dupe-keys": "error",
    "no-dupe-args": "error",
    "no-const-assign": "error",
    "no-redeclare": "error",
    "no-fallthrough": "error",
    "no-cond-assign": "error",
    "no-self-compare": "error",
    "no-compare-neg-zero": "error",
    "no-dupe-else-if": "error",
    "no-import-assign": "error",
    "no-setter-return": "error",
    "use-isnan": "error",
    "valid-typeof": "error",
    "no-async-promise-executor": "error",
    "no-case-declarations": "error",
    "no-func-assign": "error",
    "no-obj-calls": "error",
    "no-sparse-arrays": "error",
    "no-unsafe-negation": "error",
    "no-unsafe-optional-chaining": "error",
    "no-constant-condition": "error",
    "no-empty": "error",
    "no-extra-boolean-cast": "error",
    "no-irregular-whitespace": "error",
    "no-loss-of-precision": "error",
    "no-prototype-builtins": "error",
    "no-shadow-restricted-names": "error",
    "no-unused-labels": "error",
    "no-useless-escape": "error",
    "no-invalid-regexp": "error",
    "no-misleading-character-class": "error",
    "no-ex-assign": "error",
    "no-class-assign": "error",
    "no-this-before-super": "error",
    "getter-return": "error",
    "no-duplicate-case": "error",
    "array-callback-return": "error",
  },
  overrides: [
    {
      // manual-packages.js exports these on window; app.js only calls them.
      files: ["app.js"],
      globals: {
        renderManualPackages: "readonly",
        syncManualPackageValue: "readonly",
        applyManualPackageFilter: "readonly",
      },
    },
    {
      // app.js declares these at top level; manual-packages.js borrows them
      // through the shared classic-script scope described above.
      files: ["manual-packages.js"],
      globals: {
        lines: "readonly",
        updateBuildAvailability: "readonly",
        packageListEdited: "writable",
      },
    },
  ],
};
