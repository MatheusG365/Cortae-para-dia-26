type AddressContext = {
  platform: string;
  development: boolean;
  hostUri?: string | null;
  pageUrl?: string;
  configuredUrl?: string;
  port?: string;
};

/** A public API base, optionally behind a path such as /api. */
export function normalizeApiUrl(value: string) {
  const clean = value.trim();
  if (!clean || clean.includes("\\")) throw new Error("Endereço inválido.");
  const parsed = new URL(clean);
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    !/^\/[a-zA-Z0-9/_-]*$/.test(parsed.pathname)
  )
    throw new Error("Use um endereço HTTP ou HTTPS, sem senha ou parâmetros.");
  return `${parsed.origin}${parsed.pathname.replace(/\/+$/, "")}`;
}

export function resolveAutomaticApiUrl(context: AddressContext): string {
  if (context.configuredUrl?.trim())
    return normalizeApiUrl(context.configuredUrl);
  if (!context.development) {
    // The deployed website already proxies /api. Native builds need a public endpoint.
    return context.platform === "web" && context.pageUrl
      ? `${new URL(context.pageUrl).origin}/api`
      : "";
  }
  const port = context.port?.trim() || "5000";
  if (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535)
    throw new Error("A porta pública da API deve estar entre 1 e 65535.");
  let host: string;
  let protocol = "http:";
  if (context.platform === "web" && context.pageUrl) {
    const page = new URL(context.pageUrl);
    host = page.hostname;
    protocol = page.protocol;
  } else if (context.hostUri) {
    const metro = new URL(
      context.hostUri.includes("://")
        ? context.hostUri
        : `http://${context.hostUri}`,
    );
    host = metro.hostname;
    if (/(^|\.)(exp\.direct|expo\.dev|expo\.io)$/.test(host))
      throw new Error(
        "O túnel do Expo não publica a API. Use a rede local ou configure a URL pública da API no projeto.",
      );
  } else host = context.platform === "android" ? "10.0.2.2" : "127.0.0.1";
  if (
    context.platform === "android" &&
    ["localhost", "127.0.0.1", "[::1]"].includes(host)
  )
    host = "10.0.2.2";
  return normalizeApiUrl(`${protocol}//${host}:${port}`);
}
