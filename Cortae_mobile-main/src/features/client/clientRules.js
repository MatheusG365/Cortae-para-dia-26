const positiveId = (v) =>
  Number.isSafeInteger(Number(v)) && Number(v) > 0 ? Number(v) : null;
/** Deferred choices never retain a previous photo session or catalog cut. */
export function bookingChoice(params) {
  const special = ["na_hora", "profissional"].includes(params.escolha_corte);
  const cut = special ? null : positiveId(params.id_corte);
  return {
    escolha_corte: special ? params.escolha_corte : cut ? "catalogo" : null,
    id_corte: cut,
    id_visagismo: special ? null : positiveId(params.id_visagismo),
  };
}
/** Legacy booking Pix charges the full total. Do not offer it after any receipt or existing charge. */
export function canRequestBookingCharge(payment, status) {
  const balance = Number(payment.saldo),
    total = Number(payment.valor_total);
  return (
    !["cancelado", "faltou"].includes(status) &&
    payment.quitado !== true &&
    payment.parcial !== true &&
    Array.isArray(payment.cobrancas) &&
    !payment.cobrancas.length &&
    Number.isFinite(balance) &&
    balance > 0 &&
    Number.isFinite(total) &&
    total > 0 &&
    Math.abs(balance - total) < 0.005 &&
    Number(payment.valor_recebido) === 0
  );
}
export function canCreateOrderPix(order) {
  return (
    order?.status === "aguardando_pagamento" &&
    order?.pagamento_status === "nao_criado"
  );
}
export function validQuantity(quantity, stock) {
  const n = Number(quantity),
    available = Number(stock);
  return (
    Number.isSafeInteger(n) &&
    n > 0 &&
    Number.isSafeInteger(available) &&
    n <= available
  );
}
