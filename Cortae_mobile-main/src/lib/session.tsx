import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { AppState, Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import {
  api,
  ApiError,
  beginSessionChange,
  clearAccessToken,
  getSessionVersion,
  initializeApi,
  onSessionExpired,
  persistSession,
  setAccessToken,
} from "./api";

export type User = {
  id_usuario: number;
  id: number;
  nome: string;
  email: string;
  telefone: string;
  tipo: number;
  genero?: string;
  foto_perfil?: string;
};
type Session = {
  user: User | null;
  loading: boolean;
  signIn: (email: string, senha: string) => Promise<User>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
};
const SessionContext = createContext<Session | null>(null);
const USER_KEY = "cortae.user";
async function cacheUser(user: User | null) {
  if (Platform.OS === "web") {
    try {
      if (user)
        globalThis.localStorage?.setItem(USER_KEY, JSON.stringify(user));
      else globalThis.localStorage?.removeItem(USER_KEY);
    } catch {
      /* Session still works without browser persistence. */
    }
  } else if (user)
    await SecureStore.setItemAsync(USER_KEY, JSON.stringify(user));
  else await SecureStore.deleteItemAsync(USER_KEY);
}
function assertMobileUser(user: User) {
  if (![1, 2].includes(Number(user?.tipo)))
    throw new ApiError(
      "Este aplicativo é para clientes e barbearias. Utilize o site para acessar outros perfis.",
      403,
    );
}
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const clear = useCallback(async (version = beginSessionChange()) => {
    if (version !== getSessionVersion()) return;
    setUser(null);
    await Promise.all([
      clearAccessToken(version),
      persistSession(version, () => cacheUser(null)),
    ]);
  }, []);
  const refreshUser = useCallback(async () => {
    if (!user) return;
    const version = getSessionVersion();
    try {
      const result = await api<{ usuario: User }>(
        `/dados-perfil/${user.id_usuario}`,
      );
      if (version !== getSessionVersion()) return;
      assertMobileUser(result.usuario);
      if (await persistSession(version, () => cacheUser(result.usuario)))
        setUser(result.usuario);
    } catch (error) {
      if (
        version === getSessionVersion() &&
        error instanceof ApiError &&
        [401, 403].includes(error.status)
      )
        await clear();
      throw error;
    }
  }, [user, clear]);
  useEffect(() => {
    let active = true;
    const version = getSessionVersion();
    (async () => {
      try {
        await initializeApi();
        if (!active || version !== getSessionVersion()) return;
        const raw =
          Platform.OS === "web"
            ? globalThis.localStorage?.getItem(USER_KEY)
            : await SecureStore.getItemAsync(USER_KEY);
        if (raw && active && version === getSessionVersion()) {
          const cached = JSON.parse(raw) as User;
          assertMobileUser(cached);
          const fresh = await api<{ usuario: User }>(
            `/dados-perfil/${cached.id_usuario}`,
          );
          if (!active || version !== getSessionVersion()) return;
          assertMobileUser(fresh.usuario);
          if (
            (await persistSession(version, () => cacheUser(fresh.usuario))) &&
            active
          )
            setUser(fresh.usuario);
        }
      } catch (error) {
        // Cached profile is never enough to unlock the app without server validation.
        if (
          active &&
          version === getSessionVersion() &&
          error instanceof ApiError &&
          error.status !== 0 &&
          error.status < 500
        )
          await clear();
      } finally {
        if (active) setLoading(false);
      }
    })();
    const unsubscribe = onSessionExpired((expiredVersion) => {
      void clear(expiredVersion).catch(() => {});
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, [clear]);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active" && user) void refreshUser().catch(() => {});
    });
    return () => subscription.remove();
  }, [user, refreshUser, clear]);
  const signIn = useCallback(
    async (email: string, senha: string) => {
      const version = beginSessionChange();
      setUser(null);
      const assertCurrent = () => {
        if (version !== getSessionVersion())
          throw new ApiError(
            "Esta tentativa de acesso foi encerrada. Entre novamente.",
          );
      };
      try {
        await initializeApi();
        assertCurrent();
        await Promise.all([
          clearAccessToken(version),
          persistSession(version, () => cacheUser(null)),
        ]);
        assertCurrent();
        const result = await api<{ usuario: User; access_token?: string }>(
          "/login",
          { method: "POST", body: { email: email.trim(), senha } },
        );
        assertCurrent();
        assertMobileUser(result.usuario);
        if (Platform.OS !== "web") {
          if (!result.access_token)
            throw new ApiError(
              "O servidor precisa ser atualizado para permitir acesso pelo aplicativo.",
            );
          await setAccessToken(result.access_token, version);
        }
        assertCurrent();
        await persistSession(version, () => cacheUser(result.usuario));
        assertCurrent();
        setUser(result.usuario);
        return result.usuario;
      } catch (error) {
        if (version === getSessionVersion()) {
          await Promise.all([
            api("/logout", { method: "POST" }).catch(() => {}),
            clear(),
          ]);
        }
        throw error;
      }
    },
    [clear],
  );
  const signOut = useCallback(async () => {
    const remote = api("/logout", { method: "POST" });
    if (Platform.OS !== "web") {
      // Native authentication ends when its local Bearer is removed. The
      // server only removes browser cookies, so an outage must not reject logout.
      void remote.catch(() => {});
      await clear();
      return;
    }
    // A browser still needs the server to remove its HttpOnly cookie.
    await Promise.all([remote, clear()]);
  }, [clear]);
  return (
    <SessionContext.Provider
      value={{ user, loading, signIn, signOut, refreshUser }}
    >
      {children}
    </SessionContext.Provider>
  );
}
export function useSession() {
  const session = useContext(SessionContext);
  if (!session) throw new Error("Use useSession dentro de SessionProvider.");
  return session;
}
