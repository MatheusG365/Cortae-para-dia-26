export function createProductSaver({
  sessionVersion,
  apiUrl,
  message,
  update,
}) {
  let mounted = true,
    generation = 0,
    locked = false;
  let controller;
  let state = { busy: false, error: "", success: "" };
  const apply = (patch) => {
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
    setError(error) {
      if (mounted) apply({ error });
    },
    async run(action, done, text = "Alterações salvas.") {
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
