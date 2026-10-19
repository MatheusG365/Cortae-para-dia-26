/* global __dirname */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { compileJavaScript } = require("./helpers/compile.cjs");
const rules = require("../src/features/client/cardRules.js");

function nodes(tree, match) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap((item) => nodes(item, match));
  return [
    ...(match(tree) ? [tree] : []),
    ...nodes(tree.props?.children, match),
  ];
}
function harness(web, submit) {
  const values = [],
    refs = [],
    cleanups = [],
    focusCleanups = [];
  let cursor, refCursor;
  const jsx = (type, props) => ({ type, props });
  const imports = {
    react: {
      useCallback: (callback) => callback,
      useState(initial) {
        const i = cursor++;
        if (!(i in values))
          values[i] = typeof initial === "function" ? initial() : initial;
        return [
          values[i],
          (v) => {
            values[i] = typeof v === "function" ? v(values[i]) : v;
          },
        ];
      },
      useRef(initial) {
        const i = refCursor++;
        return (refs[i] ||= { current: initial });
      },
      useEffect(effect) {
        const cleanup = effect();
        if (cleanup) cleanups.push(cleanup);
      },
    },
    "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
    "react-native": { View: "View" },
    "expo-router": {
      useFocusEffect: (effect) => {
        const cleanup = effect();
        if (cleanup) focusCleanups.push(cleanup);
      },
    },
    "../../ui": {
      Button: "Button",
      Card: "Card",
      Input: "Input",
      Select: "Select",
    },
    "./common": { Heading: "Heading", Label: "Label", money: (v) => `R$ ${v}` },
    "./cardRules": rules,
    "../../services/cartaoArkhe": rules,
    "../../services/gestaoState": { dinheiro: (v) => `R$ ${v}` },
    "./CartaoArkhe.module.css": {},
  };
  const filename = path.resolve(
    __dirname,
    web
      ? "../../Frontend/src/components/CartaoArkhe/CartaoArkhe.jsx"
      : "../src/features/client/CardArkhe.jsx",
  );
  const module = { exports: {} };
  vm.runInNewContext(
    compileJavaScript(fs.readFileSync(filename, "utf8")),
    {
      module,
      exports: module.exports,
      require: (id) => {
        assert.ok(id in imports, id);
        return imports[id];
      },
    },
    { filename },
  );
  const render = () => {
    cursor = 0;
    refCursor = 0;
    return module.exports.default({ total: 100, onSubmit: submit });
  };
  function fill() {
    for (const [index, value] of [
      [0, "2481000000000001"],
      [1, "09/2031"],
      [2, "082"],
    ]) {
      const input = nodes(
        render(),
        (node) => node.type === (web ? "input" : "Input"),
      )[index];
      if (web) input.props.onChange({ target: { value } });
      else input.props.onChangeText(value);
    }
  }
  function review() {
    if (web)
      nodes(render(), (n) => n.type === "form")[0].props.onSubmit({
        preventDefault() {},
      });
    else
      nodes(
        render(),
        (n) => n.props?.title === "Conferir pagamento com cartão",
      )[0].props.onPress();
  }
  function confirm() {
    const button = nodes(render(), (n) =>
      web
        ? n.type === "button" && n.props.children === "Confirmar pagamento"
        : n.props?.title === "Confirmar pagamento",
    )[0];
    return web ? button?.props.onClick : button?.props.onPress;
  }
  return {
    fill,
    review,
    confirm,
    fields: () => values[0],
    unmount: () => cleanups.forEach((cleanup) => cleanup()),
    blur: () => focusCleanups.forEach((cleanup) => cleanup()),
  };
}
for (const web of [false, true]) {
  const name = web ? "web" : "mobile";
  test(`${name}: confirmation precedes one POST and synchronous guard blocks double press`, async () => {
    const calls = [];
    let resolve;
    const app = harness(web, (body) => {
      calls.push({ ...body });
      return new Promise((done) => {
        resolve = done;
      });
    });
    app.fill();
    assert.equal(app.confirm(), undefined);
    app.review();
    assert.equal(calls.length, 0);
    const click = app.confirm();
    assert.equal(typeof click, "function");
    const pending = click();
    const duplicate = click();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].cvv, "082");
    assert.equal(calls[0].tipo, "DEBITO");
    assert.equal(calls[0].parcelas, 1);
    assert.equal(app.fields().numero_cartao, "");
    assert.equal(app.fields().cvv, "");
    resolve();
    await pending;
    await duplicate;
    assert.equal(app.fields().validade, "");
    assert.equal(app.confirm(), undefined);
  });
  test(`${name}: failed or uncertain POST clears secrets without retry`, async () => {
    let calls = 0;
    const app = harness(web, async () => {
      calls++;
      throw new Error("Conferência necessária");
    });
    app.fill();
    app.review();
    await app.confirm()();
    assert.equal(calls, 1);
    assert.equal(app.fields().numero_cartao, "");
    assert.equal(app.fields().cvv, "");
    assert.equal(app.confirm(), undefined);
  });
  test(`${name}: unmount clears entered card data`, () => {
    const app = harness(web, async () => {
      throw new Error("Must not submit");
    });
    app.fill();
    assert.equal(app.fields().cvv, "082");
    app.unmount();
    assert.equal(app.fields().numero_cartao, "");
    assert.equal(app.fields().cvv, "");
    assert.equal(app.fields().validade, "");
  });
  test(`${name}: incomplete card cannot reach confirmation`, () => {
    const app = harness(web, async () => {
      throw new Error("Must not submit");
    });
    app.review();
    assert.equal(app.confirm(), undefined);
  });
}

test("mobile rules match booking refusal and uncertain payment contract", () => {
  const base = {
    cobrancas: [],
    saldo: 100,
    valor_total: 100,
    valor_recebido: 0,
    quitado: false,
  };
  assert.equal(
    rules.podePagarAgendamento(
      { ...base, cartao_estado: "recusado" },
      "agendado",
    ),
    true,
  );
  for (const cartao_estado of ["incerto", "processando", "aprovado"])
    assert.equal(
      rules.podePagarAgendamento({ ...base, cartao_estado }, "agendado"),
      false,
    );
  assert.equal(rules.erroCartaoIncerto({ status: 200 }), true);
  assert.equal(
    rules.erroCartaoIncerto({
      status: 400,
      data: { cartao_estado: "recusado" },
    }),
    false,
  );
});

test("mobile navigation blur clears secrets even when Expo retains the mounted screen", () => {
  const app = harness(false, async () => {
    throw new Error("Must not submit");
  });
  app.fill();
  app.review();
  app.blur();
  assert.equal(app.fields().numero_cartao, "");
  assert.equal(app.fields().cvv, "");
  assert.equal(app.confirm(), undefined);
});
