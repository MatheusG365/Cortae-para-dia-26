/* global __dirname */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

// Execute the actual button callback without a device, network or payment provider.
function harness(responses) {
  const calls = [];
  let payment = null;
  const state = {
    data: {
      cobrancas: [
        { id_financeiro: 7, descricao: "ARKHE:162 pix", valor: 23.55 },
      ],
      saldo: 23.55,
    },
    loading: false,
    error: null,
    reload: async () => {
      calls.push({ reload: true });
    },
  };
  const jsx = (type, props) => ({ type, props });
  const common = Object.fromEntries(
    ["Feedback", "Heading", "Label", "Resource"].map((name) => [name, name]),
  );
  const imports = {
    react: {
      useState: () => [
        payment,
        (value) => {
          payment = value;
        },
      ],
    },
    "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
    "react-native": { Text: "Text", View: "View" },
    "expo-clipboard": {},
    "react-native-qrcode-svg": "QRCode",
    "./clientRules": { canRequestBookingCharge: () => false },
    "../../lib/api": {
      api: async (url, options) => {
        calls.push({ url, options });
        const response = responses.shift();
        if (response instanceof Error) throw response;
        return response;
      },
    },
    "../../lib/useResource": { useResource: () => state },
    "../../ui": { Button: "Button", Card: "Card", Notice: "Notice" },
    "./common": {
      ...common,
      money: String,
      s: {},
      useAction: () => ({ run: (task) => task(), busy: false }),
    },
  };
  const filename = path.resolve(
    __dirname,
    "../src/features/client/Payment.tsx",
  );
  const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX,
    },
    fileName: filename,
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(
    compiled,
    {
      module,
      exports: module.exports,
      require: (id) => {
        assert.ok(id in imports, `Unexpected dependency: ${id}`);
        return imports[id];
      },
    },
    { filename },
  );
  const render = () =>
    module.exports.default({
      booking: { id_agendamento: 91, status: "agendado" },
    });
  function elements(tree, matches) {
    if (!tree || typeof tree !== "object") return [];
    if (Array.isArray(tree))
      return tree.flatMap((item) => elements(item, matches));
    return [
      ...(matches(tree) ? [tree] : []),
      ...elements(tree.props?.children, matches),
    ];
  }
  const consult = () =>
    elements(
      render(),
      (node) => node.props?.title === "Consultar cobrança existente",
    )[0].props.onPress();
  const codes = () =>
    elements(render(), (node) => node.type?.name === "PixCode").map(
      (node) => node.props.code,
    );
  return { calls, consult, codes };
}

test("existing charge GET restores provider QR and reloads without POST", async () => {
  const app = harness([
    { codigo_pagamento: " ARKHEPIX:EXACT-CODE ", valor: 23.55 },
  ]);
  assert.deepEqual(app.codes(), []);
  await app.consult();
  assert.deepEqual(app.calls, [
    { url: "/pagamentos/pix/162", options: undefined },
    { reload: true },
  ]);
  assert.deepEqual(app.codes(), ["ARKHEPIX:EXACT-CODE"]);
});

test("codigo_pix alias is normalized to string for QR rendering", async () => {
  const app = harness([{ codigo_pix: 12345, valor: 23.55 }]);
  await app.consult();
  assert.deepEqual(app.codes(), ["12345"]);
});

test("provider response without code clears old QR and never fabricates a replacement", async () => {
  const app = harness([
    { codigo_pagamento: "OLD" },
    { status: 0, valor: 23.55 },
  ]);
  await app.consult();
  assert.deepEqual(app.codes(), ["OLD"]);
  await app.consult();
  assert.deepEqual(app.codes(), []);
  assert.ok(
    app.calls
      .filter((call) => call.url)
      .every((call) => call.options === undefined),
  );
});

test("failed consult never creates a charge or reveals a QR", async () => {
  const app = harness([new Error("Cobrança indisponível")]);
  await assert.rejects(app.consult(), /Cobrança indisponível/);
  assert.deepEqual(app.codes(), []);
  assert.deepEqual(app.calls, [
    { url: "/pagamentos/pix/162", options: undefined },
  ]);
});
