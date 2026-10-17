import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";
import { resolveAutomaticApiUrl } from "./apiAddress";

const TOKEN_KEY = "cortae.access-token";
const SERVER_KEY = "cortae.api-url";
const MODE_KEY = "cortae.api-mode.v2";
const TOKEN_SERVER_KEY = "cortae.token-server.v2";
const USER_KEY = "cortae.user";
export function getAutomaticApiUrl() {
  return resolveAutomaticApiUrl({
    platform: Platform.OS,
    development: typeof __DEV__ !== "undefined" && __DEV__,
    hostUri: Constants.expoConfig?.hostUri,
    pageUrl: Platform.OS === "web" ? globalThis.location?.href : undefined,
    configuredUrl: process.env.EXPO_PUBLIC_API_URL,
    port: process.env.EXPO_PUBLIC_API_PORT,
  });
}
function automaticUrlOrEmpty() {
  try {
    return getAutomaticApiUrl();
  } catch {
    return "";
  }
}
let baseUrl = automaticUrlOrEmpty();
let token: string | null = null;
let initialization: Promise<void> | undefined;
let sessionVersion = 0;
let sessionWrites: Promise<unknown> = Promise.resolve();
let cookieAuthRequests: Promise<unknown> = Promise.resolve();
const expiredListeners = new Set<(version: number) => void>();

export function getSessionVersion() {
  return sessionVersion;
}

/** Invalidate requests immediately, even when a provider issues the same JWT twice. */
export function beginSessionChange() {
  token = null;
  return ++sessionVersion;
}

/** Serialize token/profile writes so a delayed native write cannot undo logout. */
export function persistSession(version: number, write: () => Promise<unknown>) {
  return queueSessionWrite(async () => {
    if (version !== sessionVersion) return false;
    await write();
    return version === sessionVersion;
  });
}

function queueSessionWrite<T>(write: () => Promise<T>) {
  const next = sessionWrites.catch(() => {}).then(write);
  sessionWrites = next;
  return next;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
    public data: any = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function messageFrom(
  data: any,
  fallback = "Não foi possível concluir. Tente novamente.",
) {
  return typeof data?.mensagem === "string"
    ? data.mensagem
    : data?.mensagem?.informacao || data?.erro || fallback;
}

async function readSetting(key: string) {
  if (Platform.OS !== "web") return SecureStore.getItemAsync(key);
  try {
    return globalThis.localStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}
async function writeSetting(key: string, value: string | null) {
  if (Platform.OS !== "web") {
    if (value === null) await SecureStore.deleteItemAsync(key);
    else await SecureStore.setItemAsync(key, value);
  } else {
    try {
      if (value === null) globalThis.localStorage?.removeItem(key);
      else globalThis.localStorage?.setItem(key, value);
    } catch {
      /* The app can connect even when browser persistence is disabled. */
    }
  }
}

export async function initializeApi() {
  if (!initialization)
    initialization = (async () => {
      const version = sessionVersion;
      const [storedToken, tokenServer] = await Promise.all([
        Platform.OS !== "web" ? readSetting(TOKEN_KEY) : null,
        readSetting(TOKEN_SERVER_KEY),
      ]);
      baseUrl = automaticUrlOrEmpty();
      // Discard both original and v2 manual overrides permanently. Only the
      // build configuration and the current Expo host select the API now.
      await queueSessionWrite(async () => {
        await writeSetting(SERVER_KEY, null);
        await writeSetting(MODE_KEY, null);
      });
      // Configuration is shared by every session. A login can already be waiting
      // for this initialization, but must never restore an older account's token.
      if (version !== sessionVersion) return;
      if (
        Platform.OS !== "web" &&
        storedToken &&
        baseUrl &&
        tokenServer === baseUrl
      )
        token = storedToken;
      else if (Platform.OS !== "web") {
        await persistSession(version, async () => {
          await writeSetting(TOKEN_KEY, null);
          await writeSetting(TOKEN_SERVER_KEY, null);
          await writeSetting(USER_KEY, null);
        });
      }
    })();
  return initialization;
}

export function getApiUrl() {
  return baseUrl;
}

function invalidateForServer(next: string) {
  if (next === baseUrl) return;
  const version = beginSessionChange();
  baseUrl = next;
  expiredListeners.forEach((listener) => listener(version));
  void persistSession(version, async () => {
    await writeSetting(TOKEN_KEY, null);
    await writeSetting(TOKEN_SERVER_KEY, null);
    await writeSetting(USER_KEY, null);
  }).catch(() => {});
}

function refreshAutomaticServer() {
  invalidateForServer(automaticUrlOrEmpty());
}

export function setAccessToken(value: string, version = sessionVersion) {
  const tokenServer = baseUrl;
  return persistSession(version, async () => {
    if (Platform.OS !== "web") {
      await SecureStore.setItemAsync(TOKEN_KEY, value);
      await SecureStore.setItemAsync(TOKEN_SERVER_KEY, tokenServer);
      if (version === sessionVersion) token = value;
    }
  });
}

export function clearAccessToken(version = beginSessionChange()) {
  if (version === sessionVersion) token = null;
  return persistSession(version, async () => {
    if (Platform.OS !== "web") {
      await SecureStore.deleteItemAsync(TOKEN_KEY);
      await SecureStore.deleteItemAsync(TOKEN_SERVER_KEY);
    }
  });
}

export function onSessionExpired(listener: (version: number) => void) {
  expiredListeners.add(listener);
  return () => {
    expiredListeners.delete(listener);
  };
}

export function query(path: string, params: Record<string, unknown> = {}) {
  const pairs = Object.entries(params)
    .filter(
      ([, value]) => value !== undefined && value !== null && value !== "",
    )
    .map(
      ([key, value]) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(Array.isArray(value) ? value.join(",") : String(value))}`,
    );
  return pairs.length
    ? `${path}${path.includes("?") ? "&" : "?"}${pairs.join("&")}`
    : path;
}

export function assetUrl(path?: string | null) {
  refreshAutomaticServer();
  if (!path) return undefined;
  if (path.startsWith("//")) return undefined;
  if (/^(https?:|data:|file:|content:|blob:)/i.test(path)) return path;
  return `${baseUrl}/${path.replace(/^\/+/, "")}`;
}

export function imageSource(uri: string): {
  uri: string;
  headers?: Record<string, string>;
} {
  refreshAutomaticServer();
  // Private visagismo files require the same native Bearer as the API. Never
  // attach credentials to external product images or arbitrary redirect URLs.
  if (Platform.OS !== "web" && token) {
    try {
      const parsed = new URL(uri);
      if (
        parsed.origin === new URL(baseUrl).origin &&
        !parsed.username &&
        !parsed.password &&
        ["fotos", "resultados"].some((folder) =>
          parsed.pathname.startsWith(
            `${new URL(baseUrl).pathname.replace(/\/+$/, "")}/uploads/visagismo/${folder}/`,
          ),
        )
      ) {
        return { uri, headers: { Authorization: `Bearer ${token}` } };
      }
    } catch {
      /* Local image sources and malformed URLs receive no credentials. */
    }
  }
  return { uri };
}

type Options = Omit<RequestInit, "body"> & {
  body?: unknown;
  timeout?: number;
  expectedSessionVersion?: number;
};
export async function api<T = any>(
  path: string,
  options: Options = {},
): Promise<T> {
  await initializeApi();
  refreshAutomaticServer();
  if (
    options.signal?.aborted ||
    (options.expectedSessionVersion !== undefined &&
      options.expectedSessionVersion !== sessionVersion)
  ) {
    throw new ApiError("A sessão mudou ou a operação foi cancelada.");
  }
  if (!baseUrl) {
    let reason =
      "A versão publicada precisa da URL pública da API na configuração do projeto.";
    try {
      getAutomaticApiUrl();
    } catch (error) {
      if (error instanceof Error) reason = error.message;
    }
    throw new ApiError(reason);
  }
  const requestVersion = sessionVersion;
  const requestBaseUrl = baseUrl;
  const requestToken = token;
  if (!path.startsWith("/") || path.startsWith("//"))
    throw new ApiError("Caminho inválido da API.");
  const {
    body,
    timeout = 30000,
    expectedSessionVersion,
    ...requestOptions
  } = options;
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (Platform.OS !== "web") {
    headers.set("X-Cortae-Client", "mobile");
    if (requestToken) headers.set("Authorization", `Bearer ${requestToken}`);
  }
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isForm)
    headers.set("Content-Type", "application/json");
  const controller = new AbortController();
  const abort = () => controller.abort();
  options.signal?.addEventListener("abort", abort);
  if (options.signal?.aborted) controller.abort();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const send = () => {
      if (
        controller.signal.aborted ||
        (expectedSessionVersion !== undefined &&
          expectedSessionVersion !== sessionVersion)
      ) {
        throw new ApiError("A sessão mudou ou a operação foi cancelada.");
      }
      timer = setTimeout(abort, timeout);
      return fetch(`${requestBaseUrl}${path}`, {
        ...requestOptions,
        headers,
        credentials: Platform.OS === "web" ? "include" : "omit",
        body:
          body === undefined
            ? undefined
            : isForm
              ? (body as FormData)
              : JSON.stringify(body),
        signal: controller.signal,
      });
    };
    // Browsers apply Set-Cookie before JS can reject a stale login result.
    // Keep login/logout responses ordered so older cookies cannot replace newer ones.
    let response: Response;
    if (Platform.OS === "web" && ["/login", "/logout"].includes(path)) {
      const pending = cookieAuthRequests.catch(() => {}).then(send);
      cookieAuthRequests = pending;
      response = await pending;
    } else response = await send();
    if (
      response.status === 401 &&
      !["/login", "/recuperar-senha", "/logout"].includes(path) &&
      requestVersion === sessionVersion &&
      requestBaseUrl === baseUrl &&
      requestToken === token
    ) {
      const version = beginSessionChange();
      const clearing = clearAccessToken(version);
      expiredListeners.forEach((listener) => listener(version));
      await clearing;
    }
    const raw = await response.text();
    let data: any = null;
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch {
        throw new ApiError(
          "O servidor retornou uma resposta inesperada.",
          response.status,
        );
      }
    }
    if (!response.ok) {
      throw new ApiError(messageFrom(data), response.status, data);
    }
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted)
      throw new ApiError(
        "A conexão demorou demais ou foi interrompida. Tente novamente.",
      );
    throw new ApiError(
      "Não foi possível conectar ao servidor. Verifique a conexão e se a API está iniciada na mesma rede.",
    );
  } finally {
    if (timer) clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}
