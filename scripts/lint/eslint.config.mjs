// Regras de ERRO para os scripts da página (extraídos por lint_code.py).
// Só pega erros reais: variável inexistente, código inalcançável, chave duplicada etc.
import globals from "globals";
const errors = {
  "no-undef": "error", "no-dupe-keys": "error", "no-unreachable": "error", "no-self-assign": "error",
  "no-dupe-else-if": "error", "no-duplicate-case": "error", "no-unsafe-finally": "error", "use-isnan": "error",
  "valid-typeof": "error", "no-loss-of-precision": "error", "no-sparse-arrays": "error",
  "no-shadow-restricted-names": "error", "getter-return": "error", "no-setter-return": "error",
  "no-unsafe-negation": "error", "no-async-promise-executor": "error", "no-const-assign": "error",
  "no-import-assign": "error", "no-dupe-class-members": "error", "no-obj-calls": "error",
  "no-unexpected-multiline": "error", "no-invalid-regexp": "error", "no-control-regex": "off",
  "constructor-super": "error", "no-this-before-super": "error", "no-unused-private-class-members": "error"
};
export default [
  { files: ["page.js"], languageOptions: { ecmaVersion: 2022, sourceType: "script",
      globals: { ...globals.browser, MISSAL_DATA: "readonly", MISSAL_STATUS: "readonly" } }, rules: errors },
  { files: ["sw.js"], languageOptions: { ecmaVersion: 2022, sourceType: "script",
      globals: { ...globals.serviceworker } }, rules: errors },
  { files: ["*.cjs"], languageOptions: { ecmaVersion: 2022, sourceType: "commonjs",
      globals: { ...globals.node, ...globals.browser } },
    // Trechos dentro de page.evaluate() usam funções da própria página.
    rules: { ...errors, "no-undef": "off" } }
];
