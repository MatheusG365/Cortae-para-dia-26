/* global __dirname */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { compileJavaScript } = require("./helpers/compile.cjs");

const tick = () => new Promise((resolve) => setImmediate(resolve));
const person = (id) => ({
  id_usuario: id,
  id,
  tipo: 1,
  nome: `Synthetic ${id}`,
});
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};

// Run real API/session modules; only React rendering, native storage and HTTP are mocked.
function harness(os = "android", initial = {}, { logoutError, env = {} } = {}) {
  const constants = { expoConfig: { hostUri: "127.0.0.1:8081" } };
  const stored = new Map(Object.entries(initial));
  const requests = [];
  const hooks = [];
  const effects = [];
  let cursor = 0;
  let pause;
  let cookieUser = null;
  const same = (a, b) =>
    a && b && a.length === b.length && a.every((v, i) => v === b[i]);
  const react = {
    createContext: () => ({ Provider: "Provider" }),
    useState: (initialValue) => {
      const at = cursor++;
      if (!hooks[at]) hooks[at] = { value: initialValue };
      return [
        hooks[at].value,
        (value) => {
          hooks[at].value = value;
        },
      ];
    },
    useCallback: (fn, deps) => {
      const at = cursor++;
      if (!same(hooks[at]?.deps, deps)) hooks[at] = { value: fn, deps };
      return hooks[at].value;
    },
    useEffect: (fn, deps) => {
      const at = cursor++;
      if (!same(hooks[at]?.deps, deps)) {
        const previous = hooks[at];
        hooks[at] = { deps };
        effects.push(() => {
          previous?.cleanup?.();
          hooks[at].cleanup = fn();
        });
      }
    },
  };
  const secure = {
    getItemAsync: async (key) => stored.get(key) ?? null,
    setItemAsync: async (key, value) => {
      if (pause?.key === key && (!pause.nonempty || value !== "null")) {
        const blocked = pause;
        pause = undefined;
        blocked.started.resolve();
        await blocked.release.promise;
      }
      stored.set(key, value);
    },
    deleteItemAsync: async (key) => {
      stored.delete(key);
    },
  };
  const localStorage = {
    getItem: (key) => stored.get(key) ?? null,
    setItem: (key, value) => stored.set(key, value),
    removeItem: (key) => stored.delete(key),
  };
  const fetch = (url, options) => {
    const response = deferred();
    const entry = {
      url,
      options,
      respond: (status, data) => {
        if (os === "web" && status === 200) {
          if (url.endsWith("/login")) cookieUser = data.usuario;
          if (url.endsWith("/logout")) cookieUser = null;
        }
        response.resolve({
          ok: status >= 200 && status < 300,
          status,
          text: async () => JSON.stringify(data),
        });
      },
    };
    requests.push(entry);
    if (url.endsWith("/logout")) {
      if (logoutError) return Promise.reject(logoutError);
      entry.respond(200, {});
    }
    return response.promise;
  };
  function compile(filename, imports) {
    const file = path.resolve(__dirname, "../src/lib", filename);
    const code = compileJavaScript(fs.readFileSync(file, "utf8"), {
      jsx: "automatic",
    });
    const module = { exports: {} };
    vm.runInNewContext(
      code,
      {
        module,
        exports: module.exports,
        process: { env },
        __DEV__: true,
        location: { href: "http://localhost:8081" },
        localStorage,
        URL,
        Headers,
        FormData,
        AbortController,
        setTimeout,
        clearTimeout,
        fetch,
        require: (id) => {
          assert.ok(id in imports, `Unexpected import ${id}`);
          return imports[id];
        },
      },
      { filename: file },
    );
    return module.exports;
  }
  const native = {
    Platform: { OS: os },
    AppState: { addEventListener: () => ({ remove() {} }) },
  };
  const address = compile("apiAddress.js", {});
  const api = compile("api.js", {
    "expo-constants": { __esModule: true, default: constants },
    "./apiAddress": address,
    "react-native": native,
    "expo-secure-store": secure,
  });
  const session = compile("session.jsx", {
    react,
    "react/jsx-runtime": { jsx: (type, props) => ({ type, props }) },
    "react-native": native,
    "expo-secure-store": secure,
    "./api": api,
  });
  const render = () => {
    cursor = 0;
    const result = session.SessionProvider({ children: null }).props.value;
    while (effects.length) effects.shift()();
    return result;
  };
  render();
  async function next(suffix) {
    for (let attempt = 0; attempt < 30; attempt++) {
      const found = requests.find(
        (request) => !request.used && request.url.endsWith(suffix),
      );
      if (found) {
        found.used = true;
        return found;
      }
      await tick();
    }
    throw new Error(`No mocked request for ${suffix}`);
  }
  async function login(id, token = "SAME-TOKEN") {
    const pending = render().signIn(`${id}@example.test`, "synthetic-password");
    (await next("/login")).respond(200, {
      usuario: person(id),
      access_token: token,
    });
    await pending;
  }
  const blockWrite = (key) => {
    pause = { key, started: deferred(), release: deferred() };
    return pause;
  };
  return {
    api,
    constants,
    stored,
    render,
    next,
    login,
    blockWrite,
    requests,
    cookieUser: () => cookieUser,
  };
}

test("refresh response after logout cannot reopen routes or cache a profile", async () => {
  const app = harness();
  await app.login(1);
  const refresh = app.render().refreshUser();
  const request = await app.next("/dados-perfil/1");
  await app.render().signOut();
  request.respond(200, { usuario: person(1) });
  await refresh;
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.user"), false);
  assert.equal(app.stored.has("cortae.access-token"), false);
});

test("native offline logout settles after clearing local authentication", async () => {
  const app = harness(
    "android",
    {},
    { logoutError: new Error("Synthetic offline") },
  );
  await app.login(1);
  await assert.doesNotReject(app.render().signOut());
  await tick();
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.access-token"), false);
  assert.equal(app.stored.has("cortae.user"), false);
});

test("web logout still reports a failure to remove its HttpOnly cookie", async () => {
  const app = harness(
    "web",
    {},
    { logoutError: new Error("Synthetic offline") },
  );
  await app.login(1);
  await assert.rejects(app.render().signOut(), /conectar ao servidor/);
  await tick();
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.user"), false);
  assert.equal(app.cookieUser().id_usuario, 1);
});

test("an in-progress native profile write is followed by logout deletion", async () => {
  const app = harness();
  await app.login(1);
  const blocked = app.blockWrite("cortae.user");
  const refresh = app.render().refreshUser();
  (await app.next("/dados-perfil/1")).respond(200, { usuario: person(1) });
  await blocked.started.promise;
  const logout = app.render().signOut();
  assert.equal(app.render().user, null);
  blocked.release.resolve();
  await Promise.all([refresh, logout]);
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.user"), false);
});

test("pending signIn response after logout cannot persist an old token", async () => {
  const app = harness();
  const login = app.render().signIn("old@example.test", "synthetic");
  const rejected = assert.rejects(login, /encerrada/);
  const request = await app.next("/login");
  await app.render().signOut();
  request.respond(200, { usuario: person(1), access_token: "OLD" });
  await rejected;
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.access-token"), false);
  assert.equal(app.stored.has("cortae.user"), false);
});

test("old signIn response cannot overwrite a newer successful login", async () => {
  const app = harness();
  const oldLogin = app.render().signIn("old@example.test", "synthetic");
  const rejected = assert.rejects(oldLogin, /encerrada/);
  const oldRequest = await app.next("/login");
  await app.login(2, "NEW");
  oldRequest.respond(200, { usuario: person(1), access_token: "OLD" });
  await rejected;
  assert.equal(app.render().user.id_usuario, 2);
  assert.equal(app.stored.get("cortae.access-token"), "NEW");
  assert.equal(JSON.parse(app.stored.get("cortae.user")).id_usuario, 2);
});

test("logout waits for an old token write and removes it without restoring user state", async () => {
  const app = harness();
  const blocked = app.blockWrite("cortae.access-token");
  const login = app.render().signIn("old@example.test", "synthetic");
  const rejected = assert.rejects(login, /encerrada/);
  (await app.next("/login")).respond(200, {
    usuario: person(1),
    access_token: "OLD",
  });
  await blocked.started.promise;
  const logout = app.render().signOut();
  blocked.release.resolve();
  await Promise.all([rejected, logout]);
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.access-token"), false);
  assert.equal(app.stored.has("cortae.user"), false);
});

test("old native token write cannot overwrite the next successful login", async () => {
  const app = harness();
  const blocked = app.blockWrite("cortae.access-token");
  const login = app.render().signIn("old@example.test", "synthetic");
  const rejected = assert.rejects(login, /encerrada/);
  (await app.next("/login")).respond(200, {
    usuario: person(1),
    access_token: "OLD",
  });
  await blocked.started.promise;
  const nextLogin = app.login(2, "NEW");
  blocked.release.resolve();
  await Promise.all([rejected, nextLogin]);
  assert.equal(app.render().user.id_usuario, 2);
  assert.equal(app.stored.get("cortae.access-token"), "NEW");
  assert.equal(JSON.parse(app.stored.get("cortae.user")).id_usuario, 2);
});

for (const os of ["android", "web"])
  test(`${os}: late 401 from prior session cannot clear new login, even with identical tokens`, async () => {
    const app = harness(os);
    await app.login(1);
    let expirations = 0;
    app.api.onSessionExpired(() => {
      expirations++;
    });
    const oldCall = app.api.api("/probe");
    const rejected = assert.rejects(oldCall, (error) => error.status === 401);
    const request = await app.next("/probe");
    await app.login(2);
    request.respond(401, { erro: "Synthetic expired" });
    await rejected;
    assert.equal(expirations, 0);
    assert.equal(app.render().user.id_usuario, 2);
    assert.equal(JSON.parse(app.stored.get("cortae.user")).id_usuario, 2);
    if (os === "android")
      assert.equal(app.stored.get("cortae.access-token"), "SAME-TOKEN");
  });

test("current-session 401 expires local user, profile cache and native token", async () => {
  const app = harness();
  await app.login(1);
  let expirations = 0;
  app.api.onSessionExpired(() => {
    expirations++;
  });
  const call = app.api.api("/probe");
  const rejected = assert.rejects(call, (error) => error.status === 401);
  (await app.next("/probe")).respond(401, { erro: "Synthetic expired" });
  await rejected;
  await tick();
  assert.equal(expirations, 1);
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.access-token"), false);
  assert.equal(app.stored.has("cortae.user"), false);
});

test("old-server 401 cannot expire the session established on a new server", async () => {
  const app = harness();
  await app.login(1);
  const oldCall = app.api.api("/probe");
  const rejected = assert.rejects(oldCall, (error) => error.status === 401);
  const request = await app.next("/probe");
  app.constants.expoConfig.hostUri = "synthetic.test:8081";
  const switched = app.api.api("/health");
  (await app.next("/health")).respond(200, {});
  await switched;
  assert.equal(app.render().user, null);
  await app.login(2, "NEW-SERVER");
  request.respond(401, { erro: "Old server" });
  await rejected;
  assert.equal(app.api.getApiUrl(), "http://synthetic.test:5000");
  assert.equal(app.render().user.id_usuario, 2);
  assert.equal(app.stored.get("cortae.access-token"), "NEW-SERVER");
});

test("automatic server change remains current when new login supersedes pending profile writes", async () => {
  const app = harness();
  await app.login(1);
  const blocked = app.blockWrite("cortae.user");
  const refresh = app.render().refreshUser();
  (await app.next("/dados-perfil/1")).respond(200, { usuario: person(1) });
  await blocked.started.promise;
  app.constants.expoConfig.hostUri = "synthetic.test:8081";
  const changing = app.api.api("/health");
  (await app.next("/health")).respond(200, {});
  await tick();
  const login = app.login(2, "NEW");
  blocked.release.resolve();
  await Promise.all([refresh, changing, login]);
  assert.equal(app.api.getApiUrl(), "http://synthetic.test:5000");
  assert.equal(
    app.stored.get("cortae.token-server.v2"),
    "http://synthetic.test:5000",
  );
  assert.equal(app.stored.has("cortae.api-url"), false);
  assert.equal(app.render().user.id_usuario, 2);
});

test("bootstrap profile response after logout is discarded", async () => {
  const app = harness("android", {
    "cortae.user": JSON.stringify(person(1)),
    "cortae.access-token": "BOOTSTRAP",
    "cortae.token-server.v2": "http://10.0.2.2:5000",
  });
  const request = await app.next("/dados-perfil/1");
  await app.render().signOut();
  request.respond(200, { usuario: person(1) });
  await tick();
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.access-token"), false);
  assert.equal(app.stored.has("cortae.user"), false);
});

test("web: login/logout cookie responses remain ordered across a late login", async () => {
  const app = harness("web");
  const login = app.render().signIn("old@example.test", "synthetic");
  const rejected = assert.rejects(login, /encerrada/);
  const oldRequest = await app.next("/login");
  const logout = app.render().signOut();
  await tick();
  assert.equal(
    app.requests.filter((request) => request.url.endsWith("/logout")).length,
    0,
  );
  oldRequest.respond(200, { usuario: person(1) });
  await Promise.all([rejected, logout]);
  assert.equal(app.cookieUser(), null);
  assert.equal(app.render().user, null);
});

test("web: newer login waits for the old login cookie and becomes the final authenticated user", async () => {
  const app = harness("web");
  const oldLogin = app.render().signIn("old@example.test", "synthetic");
  const rejected = assert.rejects(oldLogin, /encerrada/);
  const oldRequest = await app.next("/login");
  const newLogin = app.login(2);
  await tick();
  assert.equal(
    app.requests.filter((request) => request.url.endsWith("/login")).length,
    1,
  );
  oldRequest.respond(200, { usuario: person(1) });
  await Promise.all([rejected, newLogin]);
  assert.equal(app.cookieUser().id_usuario, 2);
  assert.equal(app.render().user.id_usuario, 2);
});

test("legacy saved IP and unbound token migrate to automatic without sending old credentials", async () => {
  const app = harness("android", {
    "cortae.api-url": "http://old-computer.test:5002",
    "cortae.access-token": "OLD-UNBOUND",
    "cortae.user": JSON.stringify(person(1)),
  });
  await app.api.initializeApi();
  const call = app.api.api("/health");
  const request = await app.next("/health");
  assert.equal(request.url, "http://10.0.2.2:5000/health");
  assert.equal(request.options.headers.get("Authorization"), null);
  request.respond(200, {});
  await call;
  assert.equal(app.stored.has("cortae.user"), false);
});

test("automatic Metro host change expires account and never forwards its Bearer", async () => {
  const app = harness();
  await app.login(1, "PRIVATE-TOKEN");
  app.constants.expoConfig.hostUri = "192.168.42.12:8081";
  assert.equal(app.api.getAutomaticApiUrl(), "http://192.168.42.12:5000");
  const call = app.api.api("/health");
  const request = await app.next("/health");
  assert.equal(request.url, "http://192.168.42.12:5000/health");
  assert.equal(request.options.headers.get("Authorization"), null);
  assert.equal(app.render().user, null);
  request.respond(200, {});
  await call;
  await tick();
  assert.equal(app.stored.has("cortae.access-token"), false);
  assert.equal(app.stored.has("cortae.user"), false);
});

test("token from another origin is discarded before cached profile bootstrap", async () => {
  const app = harness("android", {
    "cortae.api-mode.v2": "manual",
    "cortae.api-url": "https://other.test",
    "cortae.access-token": "OTHER-SERVER",
    "cortae.token-server.v2": "https://other.test",
    "cortae.user": JSON.stringify(person(1)),
  });
  await app.api.initializeApi();
  await tick();
  assert.equal(app.requests.length, 0);
  assert.equal(app.render().user, null);
  assert.equal(app.stored.has("cortae.access-token"), false);
});

test("legacy override migration preserves a token bound to the actual automatic server", async () => {
  const app = harness("android", {
    "cortae.api-mode.v2": "manual",
    "cortae.api-url": "https://obsolete.test",
    "cortae.access-token": "CORRECT-SERVER",
    "cortae.token-server.v2": "http://10.0.2.2:5000",
    "cortae.user": JSON.stringify(person(1)),
  });
  const request = await app.next("/dados-perfil/1");
  assert.equal(request.url, "http://10.0.2.2:5000/dados-perfil/1");
  assert.equal(
    request.options.headers.get("Authorization"),
    "Bearer CORRECT-SERVER",
  );
  request.respond(200, { usuario: person(1) });
  await tick();
  assert.equal(app.render().user.id_usuario, 1);
  assert.equal(app.stored.get("cortae.access-token"), "CORRECT-SERVER");
  assert.equal(app.stored.has("cortae.api-url"), false);
  assert.equal(app.stored.has("cortae.api-mode.v2"), false);
});

test("saved v2 manual override is ignored and permanently removed at startup", async () => {
  const app = harness("android", {
    "cortae.api-mode.v2": "manual",
    "cortae.api-url": "https://example.test/api",
  });
  await app.api.initializeApi();
  assert.equal(app.api.getApiUrl(), "http://10.0.2.2:5000");
  assert.equal(app.stored.has("cortae.api-url"), false);
  assert.equal(app.stored.has("cortae.api-mode.v2"), false);
});

test("sign-in started during bootstrap ignores manual override and its old token", async () => {
  const app = harness("android", {
    "cortae.api-mode.v2": "manual",
    "cortae.api-url": "https://selected.test/api",
    "cortae.access-token": "PREVIOUS-ACCOUNT",
    "cortae.token-server.v2": "https://selected.test/api",
  });
  const pending = app.render().signIn("new@example.test", "synthetic");
  const request = await app.next("/login");
  assert.equal(request.url, "http://10.0.2.2:5000/login");
  assert.equal(request.options.headers.get("Authorization"), null);
  request.respond(200, { usuario: person(2), access_token: "NEW" });
  await pending;
  assert.equal(app.render().user.id_usuario, 2);
});

test("private images accept the API prefix but never an outside origin or sibling path", async () => {
  const app = harness(
    "android",
    {},
    { env: { EXPO_PUBLIC_API_URL: "https://example.test/api" } },
  );
  await app.login(1, "IMAGE-TOKEN");
  assert.equal(
    app.api.imageSource(
      "https://example.test/api/uploads/visagismo/fotos/one.jpg",
    ).headers.Authorization,
    "Bearer IMAGE-TOKEN",
  );
  for (const url of [
    "https://external.test/api/uploads/visagismo/fotos/one.jpg",
    "https://example.test/uploads/visagismo/fotos/one.jpg",
    "https://example.test/api/uploads/products/one.jpg",
    "https://user:pass@example.test/api/uploads/visagismo/fotos/one.jpg",
  ]) {
    assert.equal(app.api.imageSource(url).headers, undefined);
  }
});

test("managed product relative images resolve to the API without leaking credentials", async () => {
  const app = harness(
    "android",
    {},
    { env: { EXPO_PUBLIC_API_URL: "https://example.test/api" } },
  );
  await app.login(1, "IMAGE-TOKEN");
  const filename = "a".repeat(32) + ".webp";
  const publicImage = app.api.imageSource(
    app.api.assetUrl("/uploads/marketplace/" + filename),
  );
  assert.equal(
    publicImage.uri,
    "https://example.test/api/uploads/marketplace/" + filename,
  );
  assert.equal(publicImage.headers, undefined);
  const external = app.api.imageSource(
    app.api.assetUrl("https://cdn.example.test/photo.jpg"),
  );
  assert.equal(external.uri, "https://cdn.example.test/photo.jpg");
  assert.equal(external.headers, undefined);
  const privateImage = app.api.imageSource(
    app.api.assetUrl("/uploads/visagismo/fotos/" + filename),
  );
  assert.equal(privateImage.headers.Authorization, "Bearer IMAGE-TOKEN");
});

test("prepared product cannot acquire another account token while API initialization yields", async () => {
  const app = harness("android");
  await app.login(1, "FIRST-ACCOUNT");
  const pending = app.api.api("/gestao/marketplace/produtos", {
    method: "POST",
    body: { nome: "Prepared under the first account" },
    expectedSessionVersion: app.api.getSessionVersion(),
  });
  app.api.beginSessionChange();
  await assert.rejects(pending, /A sessão mudou/);
  assert.equal(
    app.requests.some((request) =>
      request.url.endsWith("/gestao/marketplace/produtos"),
    ),
    false,
  );
});
