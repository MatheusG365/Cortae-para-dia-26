/* global __dirname */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { compileJavaScript } = require("./helpers/compile.cjs");

// Run the production queue, without a device, React mock or network side effects.
const filename = path.resolve(__dirname, "../src/lib/dialogQueue.js");
const moduleUnderTest = { exports: {} };
vm.runInNewContext(
  compileJavaScript(fs.readFileSync(filename, "utf8"), { jsx: "automatic" }),
  { module: moduleUnderTest, exports: moduleUnderTest.exports },
  { filename },
);
const { DialogQueue, confirmationOptions } = moduleUnderTest.exports;
function harness() {
  let session = 1;
  const queue = new DialogQueue(() => session);
  const calls = [];
  function show(title, onConfirm = () => calls.push(title)) {
    return queue.show({ title, message: "Descrição", onConfirm });
  }
  return { queue, calls, show, changeSession: () => session++ };
}

test("multiple requests are shown in order; repeated confirmation never executes twice", () => {
  const { queue, calls, show } = harness();
  const first = show("Primeiro");
  const second = show("Segundo");
  assert.equal(queue.getSnapshot().title, "Primeiro");
  queue.confirm(first);
  queue.confirm(first);
  assert.deepEqual(calls, ["Primeiro"]);
  assert.equal(queue.getSnapshot().id, second);
  queue.confirm(second);
  assert.deepEqual(calls, ["Primeiro", "Segundo"]);
  assert.equal(queue.getSnapshot(), null);
});

test("back, close and backdrop dismissal never invoke the action", () => {
  const { queue, calls, show } = harness();
  const first = show("Cancelar reserva");
  const second = show("Criar pedido");
  queue.dismiss(first);
  // An event captured by the old dialog cannot dismiss the next request.
  queue.dismiss(first);
  assert.equal(queue.getSnapshot().id, second);
  queue.dismiss(second);
  assert.deepEqual(calls, []);
  assert.equal(queue.getSnapshot(), null);
});

test("an in-flight double tap is ignored even when action returns a pending promise", async () => {
  const { queue, calls, show } = harness();
  let resolve;
  const pending = new Promise((done) => {
    resolve = done;
  });
  const id = show("Cobrança", () => {
    calls.push("charge");
    return pending;
  });
  queue.confirm(id);
  queue.confirm(id);
  assert.deepEqual(calls, ["charge"]);
  resolve();
  await pending;
});

test("logout or account change invalidates all old callbacks before the UI rerenders", () => {
  const { queue, calls, show, changeSession } = harness();
  const id = show("Reserva antiga");
  show("Pedido antigo");
  changeSession();
  queue.confirm(id);
  assert.deepEqual(calls, []);
  assert.equal(queue.getSnapshot(), null);
});

test("a new session request drops stale queued requests and retains its own action", () => {
  const { queue, calls, show, changeSession } = harness();
  show("Antiga");
  changeSession();
  const current = show("Atual");
  assert.equal(queue.getSnapshot().id, current);
  queue.confirm(current);
  assert.deepEqual(calls, ["Atual"]);
});

test("provider teardown clears all pending callbacks and unsubscribes notifications", () => {
  const { queue, calls, show } = harness();
  let updates = 0;
  const unsubscribe = queue.subscribe(() => updates++);
  const first = show("Primeira");
  show("Segunda");
  queue.cancelAll();
  queue.confirm(first);
  assert.equal(queue.getSnapshot(), null);
  assert.deepEqual(calls, []);
  assert.equal(updates, 3);
  unsubscribe();
  show("Terceira");
  assert.equal(updates, 3);
});

test("unexpected callback failure produces an information dialog without retrying the action", async () => {
  const { queue, show } = harness();
  let attempts = 0;
  const id = show("Falha", async () => {
    attempts++;
    throw new Error("private detail");
  });
  queue.confirm(id);
  await new Promise(setImmediate);
  assert.equal(attempts, 1);
  assert.equal(queue.getSnapshot().kind, "information");
  assert.equal(queue.getSnapshot().message.includes("private detail"), false);
  queue.confirm(queue.getSnapshot().id);
  assert.equal(attempts, 1);
  assert.equal(queue.getSnapshot(), null);
});

test("a late callback rejection after logout cannot show messages to a different account", async () => {
  const { queue, show, changeSession } = harness();
  let reject;
  const pending = new Promise((_, fail) => {
    reject = fail;
  });
  const id = show("Antiga", () => pending);
  queue.confirm(id);
  changeSession();
  reject(new Error("old request"));
  await new Promise(setImmediate);
  assert.equal(queue.getSnapshot(), null);
});

test("destructive actions have explicit labels while terms can supply their own acceptance label", () => {
  assert.equal(confirmationOptions("Cancelar atendimento?").destructive, true);
  assert.equal(
    confirmationOptions("Cancelar atendimento?").confirmLabel,
    "Cancelar atendimento",
  );
  assert.equal(
    confirmationOptions("Cliente faltou?").confirmLabel,
    "Registrar falta",
  );
  assert.equal(
    confirmationOptions("Confirmar agendamento?").destructive,
    false,
  );
});
