/* global __dirname */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function load(file, imports) {
  const source = fs.readFileSync(path.join(__dirname, "../src", file), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    require: (name) => {
      if (!(name in imports)) throw new Error(`Unexpected import ${name}`);
      return imports[name];
    },
  });
  return exports;
}

function harness() {
  const states = [];
  const effects = [];
  let cursor = 0;
  let base = "";
  let resolve;
  const ready = new Promise((done) => {
    resolve = done;
  });
  const listeners = new Set();
  const appListeners = new Set();
  const react = {
    useState: (initial) => {
      const index = cursor++;
      if (!(index in states)) states[index] = initial;
      return [
        states[index],
        (value) => {
          states[index] = value;
        },
      ];
    },
    useEffect: (effect) => {
      if (!effects.length) effects.push(effect());
    },
    createElement: (type, props, ...children) => ({
      type,
      props: props || {},
      children,
    }),
  };
  const api = {
    initializeApi: () => ready,
    onSessionExpired: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getApiUrl: () => base,
    assetUrl: (uri) =>
      !uri ? undefined : /^https?:/.test(uri) ? uri : `${base}${uri}`,
    imageSource: (uri) => ({ uri }),
  };
  const native = {
    AppState: {
      addEventListener: (_, listener) => {
        appListeners.add(listener);
        return { remove: () => appListeners.delete(listener) };
      },
    },
    Image: "Image",
    View: "View",
    Text: "Text",
    StyleSheet: { create: (styles) => styles },
  };
  const assets = load("lib/mobileAssets.ts", { "./api": api });
  const hook = load("lib/useMobileAsset.ts", {
    react,
    "react-native": native,
    "./api": api,
    "./mobileAssets": assets,
  });
  const ui = load("ui.tsx", {
    react,
    "react-native": native,
    "./lib/api": api,
    "react-native-safe-area-context": {},
    "@expo/vector-icons/Ionicons": "Icon",
    "expo-router": {},
    "./theme": { colors: {}, fonts: {} },
  });
  return {
    assets,
    hook,
    ui,
    render(fn) {
      cursor = 0;
      return fn();
    },
    async initialize(url) {
      base = url;
      resolve();
      await ready;
      await Promise.resolve();
    },
    changeServer(url) {
      base = url;
      listeners.forEach((listener) => listener());
    },
    foreground(url) {
      base = url;
      appListeners.forEach((listener) => listener("active"));
    },
    unmount() {
      effects.forEach((cleanup) => cleanup?.());
    },
    listenerCount: () => listeners.size + appListeners.size,
  };
}

test("mobile content waits for API initialization and uses canonical backend aliases", async () => {
  const h = harness();
  const render = () => h.render(() => h.hook.useMobileAsset("logo"));
  assert.equal(render(), undefined);
  assert.equal(h.assets.mobileAssetUrl("logo"), undefined);
  await h.initialize("https://api.example.test/cortae");
  assert.equal(
    render(),
    "https://api.example.test/cortae/midia/mobile/logo-cortae.png",
  );
  assert.equal(
    h.assets.mobileAssetUrl("banner"),
    "https://api.example.test/cortae/midia/mobile/banner-1.png",
  );
});

test("public assets follow automatic server changes and foreground refresh; subscriptions clean up", async () => {
  const h = harness();
  const render = () => h.render(() => h.hook.useMobileAsset("logo"));
  render();
  await h.initialize("https://one.example.test");
  assert.match(render(), /^https:\/\/one\./);
  h.changeServer("https://two.example.test");
  assert.match(render(), /^https:\/\/two\./);
  h.foreground("https://three.example.test");
  assert.match(render(), /^https:\/\/three\./);
  h.unmount();
  assert.equal(h.listenerCount(), 0);
});

test("unmounted assets ignore pending API initialization", async () => {
  const h = harness();
  const render = () => h.render(() => h.hook.useMobileAsset("logo"));
  render();
  h.unmount();
  await h.initialize("https://later.example.test");
  assert.equal(render(), undefined);
});

test("image failure has accessible brand fallback and a new server retries the same relative path", async () => {
  const h = harness();
  await h.initialize("https://one.example.test");
  const render = () =>
    h.render(() =>
      h.ui.RemoteImage({
        uri: "/midia/mobile/logo-cortae.png",
        fallback: "CORTAÊ",
        accessibilityLabel: "Cortaê",
      }),
    );
  const first = render();
  assert.equal(first.type, "Image");
  assert.equal(
    first.props.source.uri,
    "https://one.example.test/midia/mobile/logo-cortae.png",
  );
  first.props.onError();
  const failed = render();
  assert.equal(failed.type, "View");
  assert.equal(failed.children[0].props.accessibilityLabel, "Cortaê");
  assert.equal(failed.children[0].children[0], "CORTAÊ");
  h.changeServer("https://two.example.test");
  assert.equal(render().type, "Image");
  // A delayed event from the previous Image must not hide the new source.
  first.props.onError();
  assert.equal(
    render().props.source.uri,
    "https://two.example.test/midia/mobile/logo-cortae.png",
  );
});
