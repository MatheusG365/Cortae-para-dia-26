export type ProductSaveState = {
  busy: boolean;
  error: string;
  success: string;
};
export type ProductSaveContext = {
  current: () => boolean;
  sessionVersion: number;
  signal: AbortSignal;
};
export function createProductSaver({
  sessionVersion,
  apiUrl,
  message,
  update,
}: {
  sessionVersion: () => number;
  apiUrl: () => string;
  message: (error: unknown) => string;
  update: (state: ProductSaveState) => void;
}) {
  let mounted = true,
    generation = 0,
    locked = false;
  let controller: AbortController | undefined;
  let state: ProductSaveState = { busy: false, error: "", success: "" };
  const apply = (patch: Partial<ProductSaveState>) => {
    state = { ...state, ...patch };
    update(state);
  };
  return {
    mount() {
      mounted = true;
    },
    dispose() {
      mounted = false;
      generation++;
      controller?.abort();
    },
    setError(error: string) {
      if (mounted) apply({ error });
    },
    async run(
      action: (context: ProductSaveContext) => Promise<unknown>,
      done?: () => unknown,
      text = "Alterações salvas.",
    ) {
      if (!mounted || locked) return false;
      const server = apiUrl(),
        version = sessionVersion(),
        ticket = generation;
      const current = () =>
        mounted &&
        ticket === generation &&
        apiUrl() === server &&
        sessionVersion() === version;
      controller = new AbortController();
      locked = true;
      apply({ busy: true, error: "", success: "" });
      try {
        await action({
          current,
          sessionVersion: version,
          signal: controller.signal,
        });
        if (!current()) return false;
        await done?.();
        if (!current()) return false;
        apply({ success: text });
        return true;
      } catch (error) {
        if (current()) apply({ error: message(error) });
        return false;
      } finally {
        locked = false;
        if (current()) apply({ busy: false });
      }
    },
  };
}
