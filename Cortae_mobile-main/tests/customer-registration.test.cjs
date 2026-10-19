const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { compileJavaScript } = require("./helpers/compile.cjs");
const validation = require("../src/features/auth/validation.js");

const form = {
  nome: " Cliente Teste ",
  email: " qa@example.invalid ",
  telefone: "11912345678",
  senha: "Ficticio123!",
  confirmar: "Ficticio123!",
  genero: "",
  aceito: true,
  tipo: 2,
};
test("customer payload ignores injected privileged roles and preserves explicit current terms", () => {
  for (const tipo of [0, 2, 3, "2"]) {
    const result = validation.customerRegistration(
      { ...form, tipo },
      { aceite_habilitado: true, versao: "qa-current" },
    );
    assert.equal(result.tipo, 1);
    assert.equal(result.nome, "Cliente Teste");
    assert.equal(result.email, "qa@example.invalid");
    assert.equal(result.termos_versao, "qa-current");
    assert.equal(result.termos_aceitos, true);
    assert.equal(result.confirmarSenha, form.confirmar);
  }
  assert.equal(
    validation.customerRegistration(form, { aceite_habilitado: false })
      .termos_aceitos,
    undefined,
  );
});

function harness({
  terms = { aceite_habilitado: false, versao: "qa-draft" },
  accepted = false,
} = {}) {
  const values = [
    "Cliente Teste",
    "qa@example.invalid",
    "11912345678",
    "Ficticio123!",
    "Ficticio123!",
    accepted,
    false,
    "",
  ];
  const calls = [],
    destinations = [];
  let cursor = 0;
  const jsx = (type, props) => ({ type, props });
  const imports = {
    react: {
      useState: () => {
        const index = cursor++;
        return [
          values[index],
          (value) => {
            values[index] = value;
          },
        ];
      },
    },
    "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
    "react-native": { Pressable: "Pressable", Text: "Text", View: "View" },
    "expo-router": { router: { replace: (value) => destinations.push(value) } },
    "../ui": {
      Button: "Button",
      Input: "Input",
      Notice: "Notice",
      Select: "Select",
    },
    "../lib/api": {
      api: async (url, options) => {
        calls.push({ url, ...options });
        return {};
      },
    },
    "../lib/useResource": {
      useResource: () => ({ data: terms, loading: false }),
    },
    "../features/auth/styles": { authStyles: {} },
    "../features/auth/AuthScreen": "AuthScreen",
    "../features/auth/validation": validation,
  };
  const module = { exports: {} };
  vm.runInNewContext(
    compileJavaScript(
      fs.readFileSync(path.join(__dirname, "../src/app/cadastro.jsx"), "utf8"),
    ),
    {
      module,
      exports: module.exports,
      require: (name) => {
        assert.ok(name in imports, name);
        return imports[name];
      },
    },
  );
  const render = () => {
    cursor = 0;
    return module.exports.default();
  };
  function elements(tree) {
    if (!tree || typeof tree !== "object") return [];
    if (Array.isArray(tree)) return tree.flatMap(elements);
    return [tree, ...elements(tree.props?.children)];
  }
  const nodes = () => elements(render());
  return { calls, destinations, nodes };
}

test("native registration offers no business/admin choice and submits only a customer", async () => {
  const h = harness();
  for (const select of h.nodes().filter((node) => node.type === "Select")) {
    assert.ok(
      select.props.options.every(
        (option) => !["1", "2", "0", "3"].includes(option.value),
      ),
    );
  }
  h.nodes()
    .find(
      (node) => node.type === "Button" && node.props.title === "CRIAR CONTA",
    )
    .props.onPress();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].url, "/cadastro");
  assert.equal(h.calls[0].body.tipo, 1);
  assert.equal(h.destinations[0].pathname, "/verificar-codigo");
});

test("published terms still block registration until explicitly accepted", async () => {
  const h = harness({
    terms: { aceite_habilitado: true, versao: "qa-current" },
  });
  h.nodes()
    .find(
      (node) => node.type === "Button" && node.props.title === "CRIAR CONTA",
    )
    .props.onPress();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(h.calls.length, 0);
  assert.equal(
    h.nodes().find((node) => node.type === "Notice").props.message,
    "Leia e aceite os termos de uso.",
  );
});
