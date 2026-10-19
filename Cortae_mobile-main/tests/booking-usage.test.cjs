const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { compileJavaScript } = require("./helpers/compile.cjs");
const rules = require("../src/features/client/clientRules.js");

function elements(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(elements);
  return [tree, ...elements(tree.props?.children)];
}

function harness({ reschedule = false, staffError = null, staff = [] } = {}) {
  const summary = { confirmacao_resumo: "fictional-qa" };
  const values = reschedule
    ? ["2026-10-18", true, "14:00"]
    : ["", "2026-10-18", true, "14:00", summary, false, null];
  const paths = [];
  let cursor = 0;
  const jsx = (type, props) => ({ type, props });
  const localDate = (value = new Date(2026, 9, 18, 12)) =>
    `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  const imports = {
    react: {
      useState: () => {
        const index = cursor++;
        return [values[index], (value) => (values[index] = value)];
      },
    },
    "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
    "react-native": { View: "View" },
    "@react-native-community/datetimepicker": "DateTimePicker",
    "expo-router": {
      useLocalSearchParams: () => ({ barbearia: "2", servicos: "1" }),
    },
    "../../lib/api": {
      api: () => assert.fail("This render must not write to the API"),
      query: (url, params) => `${url}?${new URLSearchParams(params)}`,
    },
    "../../lib/useResource": {
      useResource: (url) => {
        paths.push(url);
        return !reschedule && paths.length === 1
          ? { data: { funcionarios: staff }, loading: false, error: staffError }
          : {
              data: { horarios: [], servicos: [] },
              loading: false,
              error: null,
            };
      },
    },
    "../../ui": Object.fromEntries(
      [
        "Button",
        "Card",
        "Input",
        "Notice",
        "RemoteImage",
        "Screen",
        "Select",
      ].map((name) => [name, name]),
    ),
    "./clientRules": rules,
    "./Payment": "Payment",
    "./common": {
      ...Object.fromEntries(
        [
          "Feedback",
          "Heading",
          "Label",
          "Resource",
          "Summary",
          "TermsConsent",
        ].map((name) => [name, name]),
      ),
      localDate,
      s: {},
      useAction: () => ({ busy: false }),
    },
  };
  const filename = reschedule ? "Appointments.jsx" : "Booking.jsx";
  let source = fs.readFileSync(
    path.join(__dirname, "../src/features/client", filename),
    "utf8",
  );
  // Expose the existing internal component only in this isolated test module.
  if (reschedule) source += "\nexport { Reschedule as TestedReschedule };";
  const module = { exports: {} };
  vm.runInNewContext(compileJavaScript(source), {
    module,
    exports: module.exports,
    require: (name) => {
      assert.ok(name in imports, name);
      return imports[name];
    },
    URLSearchParams,
  });
  const render = () => {
    cursor = 0;
    paths.length = 0;
    return reschedule
      ? module.exports.TestedReschedule({
          item: { id_barbearia: 2, servicos: [1] },
        })
      : module.exports.default();
  };
  const picker = () =>
    elements(render()).find((node) => node.type === "DateTimePicker").props;
  return { render, picker, values, paths, summary };
}

for (const reschedule of [false, true]) {
  const name = reschedule ? "rescheduling" : "booking";
  test(`${name}: cancelling the native calendar preserves the selected slot`, () => {
    const h = harness({ reschedule });
    const picker = h.picker();
    // The installed native picker passes the original date to legacy onChange on cancel.
    if (picker.onDismiss) picker.onDismiss();
    else picker.onChange({ type: "dismissed" }, picker.value);
    const offset = reschedule ? 0 : 1;
    assert.equal(h.values[offset], "2026-10-18");
    assert.equal(h.values[offset + 1], false);
    assert.equal(h.values[offset + 2], "14:00");
    if (!reschedule) assert.equal(h.values[4], h.summary);
  });

  test(`${name}: confirming another date clears the old slot and summary`, () => {
    const h = harness({ reschedule });
    const picker = h.picker();
    (picker.onValueChange || picker.onChange)(
      { type: "set" },
      new Date(2026, 9, 22, 12),
    );
    const offset = reschedule ? 0 : 1;
    assert.equal(h.values[offset], "2026-10-22");
    assert.equal(h.values[offset + 1], false);
    assert.equal(h.values[offset + 2], "");
    if (!reschedule) assert.equal(h.values[4], null);
  });
}

test("failed staff lookup does not request unassigned appointment slots", () => {
  const h = harness({ staffError: "503: simulated staff failure" });
  h.render();
  assert.equal(h.paths[1], null);
});

test("confirmed empty staff list still allows unassigned availability lookup", () => {
  const h = harness();
  h.render();
  assert.ok(h.paths[1].startsWith("/agendamentos/horarios?"));
});
