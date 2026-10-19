const test = require("node:test");
const assert = require("node:assert/strict");
const {
  bookingChoice,
  canRequestBookingCharge,
  canCreateOrderPix,
  validQuantity,
} = require("../src/features/client/clientRules.js");
test("deferred cut removes old catalog and photo session", () => {
  for (const choice of ["na_hora", "profissional"])
    assert.deepEqual(
      bookingChoice({
        escolha_corte: choice,
        id_corte: "5",
        id_visagismo: "9",
      }),
      { escolha_corte: choice, id_corte: null, id_visagismo: null },
    );
});
test("color-only session keeps session without inventing a cut", () =>
  assert.deepEqual(bookingChoice({ id_visagismo: "9" }), {
    escolha_corte: null,
    id_corte: null,
    id_visagismo: 9,
  }));
test("catalog choice validates positive IDs", () => {
  assert.deepEqual(bookingChoice({ id_corte: "5", id_visagismo: "9" }), {
    escolha_corte: "catalogo",
    id_corte: 5,
    id_visagismo: 9,
  });
  assert.equal(bookingChoice({ id_corte: "NaN" }).id_corte, null);
});
const pending = {
  cobrancas: [],
  saldo: 50,
  valor_total: 50,
  valor_recebido: 0,
  quitado: false,
  parcial: false,
};
test("only untouched unpaid booking can request first full charge", () =>
  assert.equal(canRequestBookingCharge(pending, "agendado"), true));
test("partial receipt never requests full total again", () => {
  assert.equal(
    canRequestBookingCharge(
      { ...pending, saldo: 40, valor_recebido: 10 },
      "agendado",
    ),
    false,
  );
  assert.equal(
    canRequestBookingCharge({ ...pending, parcial: true }, "agendado"),
    false,
  );
});
test("existing charge, paid, cancelled or absent booking cannot create another", () => {
  for (const p of [
    { ...pending, cobrancas: [{ status: 0 }] },
    { ...pending, quitado: true },
    { ...pending, saldo: 0 },
  ])
    assert.equal(canRequestBookingCharge(p, "agendado"), false);
  for (const status of ["cancelado", "faltou"])
    assert.equal(canRequestBookingCharge(pending, status), false);
});
test("unknown payment state and nonfinite amounts do not allow charge", () => {
  assert.equal(canRequestBookingCharge({}, "agendado"), false);
  for (const value of [NaN, Infinity, -1])
    assert.equal(
      canRequestBookingCharge({ ...pending, saldo: value }, "agendado"),
      false,
    );
});
test("marketplace reuses processing/pending charges, creates only when absent", () => {
  assert.equal(
    canCreateOrderPix({
      status: "aguardando_pagamento",
      pagamento_status: "nao_criado",
    }),
    true,
  );
  for (const status of ["processando", "pendente", "pago", "falhou"])
    assert.equal(
      canCreateOrderPix({
        status: "aguardando_pagamento",
        pagamento_status: status,
      }),
      false,
    );
  assert.equal(
    canCreateOrderPix({ status: "cancelado", pagamento_status: "nao_criado" }),
    false,
  );
});
test("cart quantity must be integer, positive and within variation stock", () => {
  assert.equal(validQuantity("2", 3), true);
  for (const value of ["0", "-1", "2.5", "abc", "Infinity", "4"])
    assert.equal(validQuantity(value, 3), false);
  assert.equal(validQuantity(1, 0), false);
});
