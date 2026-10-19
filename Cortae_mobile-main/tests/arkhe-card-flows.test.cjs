/* global __dirname */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { compileJavaScript } = require("./helpers/compile.cjs");
const rules = require("../src/features/client/cardRules.js");
const clientRules = require("../src/features/client/clientRules.js");
const fields = {
  numero_cartao: "2481000000000001",
  validade: "09/2031",
  cvv: "082",
  tipo: "CREDITO",
  parcelas: 3,
  valor: 0.01,
  pin: "1234",
};
const receipt = {
  metodo: "cartao",
  aprovado: true,
  status: 1,
  cartao_estado: "aprovado",
  valor: 100,
  valor_recebido: 95,
  taxa: 5,
  tipo: "CREDITO",
  parcelas: 3,
  final_cartao: "0001",
  id_compra: 456,
  id_movimentacao: 789,
};
const booking = {
  quitado: false,
  parcial: false,
  saldo: 100,
  valor_total: 100,
  valor_recebido: 0,
  cobrancas: [],
  cartao_estado: null,
};
const order = {
  id_pedido: 7,
  total: 100,
  status: "aguardando_pagamento",
  pagamento_status: "nao_criado",
  itens: [],
};
function nodes(tree, match) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap((item) => nodes(item, match));
  return [
    ...(match(tree) ? [tree] : []),
    ...nodes(tree.props?.children, match),
  ];
}
function harness(
  kind,
  { refused = false, uncertain = false, existing = false } = {},
) {
  const web = kind.startsWith("web"),
    isOrder = kind.endsWith("order");
  const values = [],
    refs = [],
    calls = [];
  let cursor,
    refCursor,
    posted = false;
  const state = {
    data: isOrder ? { pedido: order } : booking,
    dados: isOrder ? { pedido: order } : booking,
    loading: false,
    error: null,
  };
  const result = () =>
    isOrder
      ? {
          pedido: {
            ...order,
            pagamento_status: refused
              ? "recusado"
              : uncertain
                ? "incerto"
                : "pago",
            pagamento:
              refused || uncertain
                ? {
                    metodo: "cartao",
                    cartao_estado: refused ? "recusado" : "incerto",
                  }
                : receipt,
          },
          pagamento: receipt,
        }
      : {
          ...booking,
          cartao_estado: refused
            ? "recusado"
            : uncertain
              ? "incerto"
              : "aprovado",
          cartao_resultado: refused || uncertain ? null : receipt,
        };
  state.reload = async () => {
    if (posted) state.data = result();
    calls.push({ reload: true });
  };
  state.recarregar = () => {
    if (posted) state.dados = result();
    calls.push({ reload: true });
  };
  state.setData = (value) => {
    state.data = value;
  };
  async function api(url, options) {
    calls.push({
      url,
      options: options ? JSON.parse(JSON.stringify(options)) : undefined,
    });
    if (options?.method === "POST") {
      posted = true;
      if (refused || uncertain) {
        const error = new Error(
          refused ? "Cartão recusado" : "Resultado incerto",
        );
        error.status = refused ? 400 : 502;
        error.data = error.dados = {
          cartao_estado: refused ? "recusado" : "incerto",
        };
        throw error;
      }
      return isOrder ? result() : receipt;
    }
    if (posted) return result();
    return isOrder
      ? {
          pedido: existing ? { ...order, pagamento_status: "pendente" } : order,
        }
      : existing
        ? { ...booking, cobrancas: [{ status: 0 }] }
        : booking;
  }
  const jsx = (type, props) => ({ type, props });
  const imports = {
    react: {
      useState(initial) {
        const i = cursor++;
        if (!(i in values))
          values[i] =
            !isOrder && web && i === 0
              ? booking
              : typeof initial === "function"
                ? initial()
                : initial;
        return [
          values[i],
          (value) => {
            values[i] = typeof value === "function" ? value(values[i]) : value;
          },
        ];
      },
      useRef(initial) {
        const i = refCursor++;
        return (refs[i] ||= { current: initial });
      },
      useEffect() {},
    },
    "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
    "react-native": { View: "View", Text: "Text" },
    "expo-clipboard": {},
    "react-native-qrcode-svg": "QRCode",
    "qrcode.react": { QRCodeSVG: "QRCode" },
    "expo-router": { useLocalSearchParams: () => ({ id: "7" }) },
    "react-router-dom": { Link: "Link", useParams: () => ({ id: "7" }) },
    "../../lib/api": { api, assetUrl: (x) => x },
    "../../services/api": {
      apiFetch: api,
      mensagemDaApi: (error) => error.message,
    },
    "../../lib/useResource": { useResource: () => state },
    "./useMarketplace": () => state,
    "../../contexts/useAuth": { useAuth: () => ({ usuario: { tipo: 1 } }) },
    "../../services/pagamentoState": {
      estadoPagamento: () => "Pendente",
      podeConfirmarRecebimento: () => false,
    },
    "../../services/gestaoState": { dinheiro: String },
    "../../services/formatacao": { dinheiroZero: String },
    "../../services/cartaoArkhe": rules,
    "./cardRules": rules,
    "./clientRules": clientRules,
    "../CartaoArkhe/CartaoArkhe": {
      __esModule: true,
      default: "CardForm",
      ReciboCartao: "Receipt",
    },
    "../../components/CartaoArkhe/CartaoArkhe": {
      __esModule: true,
      default: "CardForm",
      ReciboCartao: "Receipt",
    },
    "./CardArkhe": {
      __esModule: true,
      default: "CardForm",
      CardReceipt: "Receipt",
    },
    "../ResumoTaxa/ResumoTaxa": "Summary",
    "../../components/ResumoTaxa/ResumoTaxa": "Summary",
    "./Payment": { PixCode: "PixCode" },
    "../../ui": {
      Button: "Button",
      Card: "Card",
      Notice: "Notice",
      Screen: "Screen",
      RemoteImage: "RemoteImage",
    },
    "./common": {
      Feedback: "Feedback",
      Heading: "Heading",
      Label: "Label",
      Resource: "Resource",
      Summary: "Summary",
      money: String,
      dateTime: String,
      s: {},
      useAction: () => ({ run: (task) => task(), busy: false }),
    },
    "./comercialState": { nomeVariacao: () => "" },
    "./marketplaceApi": {
      marketplace: api,
      json: (method, body) => ({ method, body: JSON.stringify(body) }),
    },
    "./MarketplaceUI": Object.fromEntries(
      ["Aviso", "Carregamento", "FotoProduto", "LojaLayout", "ModalLoja"].map(
        (k) => [k, k],
      ),
    ),
    "./marketplaceState": {
      moeda: String,
      dataHora: String,
      statusPedido: {},
      statusPagamento: {},
      pagamentoDoPedido: (id, p, cache) => cache?.dados || p?.pagamento,
    },
    "./PagamentoAgendamento.module.css": {},
    "./Marketplace.module.css": {},
  };
  const files = {
    "web-booking":
      "../../Frontend/src/components/PagamentoAgendamento/PagamentoAgendamento.jsx",
    "web-order": "../../Frontend/src/pages/Marketplace/MarketplacePedidos.jsx",
    "mobile-booking": "../src/features/client/Payment.jsx",
    "mobile-order": "../src/features/client/Orders.jsx",
  };
  const filename = path.resolve(__dirname, files[kind]),
    module = { exports: {} };
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
  function render() {
    cursor = 0;
    refCursor = 0;
    const props = web
      ? { agendamento: { id_agendamento: 91, status: "agendado" } }
      : { booking: { id_agendamento: 91, status: "agendado" } };
    const screen = module.exports.default(props);
    return typeof screen.type === "function"
      ? screen.type(screen.props)
      : screen;
  }
  const card = () => nodes(render(), (n) => n.type === "CardForm")[0];
  return { calls, card, render };
}
for (const kind of [
  "web-booking",
  "web-order",
  "mobile-booking",
  "mobile-order",
]) {
  test(`${kind}: POST contains exact card fields, trusted booking id and no client amount/PIN`, async () => {
    const app = harness(kind);
    const card = app.card();
    assert.ok(card);
    await card.props.onSubmit({ ...fields });
    const posts = app.calls.filter((call) => call.options?.method === "POST");
    assert.equal(posts.length, 1);
    const body =
      typeof posts[0].options.body === "string"
        ? JSON.parse(posts[0].options.body)
        : posts[0].options.body;
    assert.equal(body.numero_cartao, fields.numero_cartao);
    assert.equal(body.cvv, "082");
    assert.equal(body.parcelas, 3);
    assert.equal(body.tipo, "CREDITO");
    assert.equal(Object.hasOwn(body, "valor"), false);
    assert.equal(Object.hasOwn(body, "pin"), false);
    assert.equal(
      body.id_agendamento,
      kind.endsWith("booking") ? 91 : undefined,
    );
    assert.match(
      posts[0].url,
      kind.endsWith("booking")
        ? /^\/pagamentos\/cartao$/
        : /\/pedidos\/7\/cartao$/,
    );
  });
  test(`${kind}: fresh existing charge stops stale card action before POST`, async () => {
    const app = harness(kind, { existing: true });
    await app
      .card()
      .props.onSubmit({ ...fields })
      .catch(() => {});
    assert.equal(
      app.calls.filter((call) => call.options?.method === "POST").length,
      0,
    );
  });
  test(`${kind}: ambiguous response blocks new card until reconciliation`, async () => {
    const app = harness(kind, { uncertain: true });
    await app
      .card()
      .props.onSubmit({ ...fields })
      .catch(() => {});
    assert.equal(
      app.calls.filter((call) => call.options?.method === "POST").length,
      1,
    );
    assert.equal(app.card(), undefined);
    assert.equal(
      app.calls.some((call) => /cartao\//.test(call.url || "")),
      false,
    );
  });
  test(`${kind}: deterministic rejection allows explicit new payment after refresh`, async () => {
    const app = harness(kind, { refused: true });
    await app
      .card()
      .props.onSubmit({ ...fields })
      .catch(() => {});
    assert.ok(app.card());
    assert.equal(
      app.calls.filter((call) => call.options?.method === "POST").length,
      1,
    );
  });
}
