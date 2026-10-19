/* global __dirname */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { compileJavaScript } = require("./helpers/compile.cjs");
const source = fs.readFileSync(
  path.resolve(__dirname, "../src/lib/apiAddress.js"),
  "utf8",
);
const moduleUnderTest = { exports: {} };
vm.runInNewContext(compileJavaScript(source, { jsx: "automatic" }), {
  module: moduleUnderTest,
  exports: moduleUnderTest.exports,
  URL,
});
const { resolveAutomaticApiUrl: resolve, normalizeApiUrl: normalize } =
  moduleUnderTest.exports;
const dev = { platform: "android", development: true };

test("native LAN follows the Metro computer without a hardcoded IP", () => {
  for (const host of [
    "192.168.0.23",
    "10.0.1.6",
    "studio.local",
    "[2001:db8::12]",
  ])
    assert.equal(
      resolve({ ...dev, hostUri: `${host}:8081` }),
      `http://${host}:5000`,
    );
});
test("Android localhost aliases target the emulator computer; iOS keeps localhost", () => {
  for (const hostUri of ["localhost:8081", "127.0.0.1:8081", "[::1]:8081"])
    assert.equal(resolve({ ...dev, hostUri }), "http://10.0.2.2:5000");
  assert.equal(
    resolve({ ...dev, platform: "ios", hostUri: "localhost:8081" }),
    "http://localhost:5000",
  );
});
test("web development follows the current browser host and API port", () => {
  assert.equal(
    resolve({
      ...dev,
      platform: "web",
      pageUrl: "http://192.168.0.22:8081/entrar",
      port: "5050",
    }),
    "http://192.168.0.22:5050",
  );
  assert.equal(
    resolve({ ...dev, platform: "web", pageUrl: "https://dev.example:8081" }),
    "https://dev.example:5000",
  );
});
test("published native builds need one public endpoint, never infer Metro in production", () => {
  assert.equal(
    resolve({ ...dev, development: false, hostUri: "192.168.1.10:8081" }),
    "",
  );
  assert.equal(
    resolve({
      ...dev,
      development: false,
      configuredUrl: "https://api.example/api/",
    }),
    "https://api.example/api",
  );
  assert.equal(
    resolve({
      ...dev,
      development: false,
      platform: "web",
      pageUrl: "https://cortae.example/loja",
    }),
    "https://cortae.example/api",
  );
});
test("explicit public endpoint overrides development detection", () => {
  assert.equal(
    resolve({
      ...dev,
      hostUri: "localhost:8081",
      configuredUrl: "https://api.example/v1/",
    }),
    "https://api.example/v1",
  );
});
test("Expo tunnels are not mistaken for an API tunnel", () => {
  assert.throws(
    () => resolve({ ...dev, hostUri: "abc.exp.direct:80" }),
    /túnel/,
  );
});
test("invalid API ports and unsafe endpoint URLs are rejected", () => {
  for (const port of ["0", "65536", "abc", "5000/path"])
    assert.throws(() => resolve({ ...dev, port }));
  for (const url of [
    "ftp://example.test",
    "https://user:pass@example.test",
    "https://example.test/?secret=yes",
    "https://example.test/#fragment",
    "https://example.test\\evil",
    "//example.test",
  ])
    assert.throws(() => normalize(url));
  assert.equal(normalize(" http://[::1]:5000/api/ "), "http://[::1]:5000/api");
});
