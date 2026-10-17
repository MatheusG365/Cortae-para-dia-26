export type DialogOptions = {
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  kind?: "confirmation" | "information" | "terms";
};
export type DialogRequest = DialogOptions & {
  title: string;
  message: string;
  onConfirm?: () => void | Promise<unknown>;
};
export type QueuedDialog = DialogRequest & { id: number; session: number };

/** Each request belongs to the session that opened it, including queued requests. */
export class DialogQueue {
  private requests: QueuedDialog[] = [];
  private listeners = new Set<() => void>();
  private nextId = 0;
  constructor(private getSession: () => number) {}
  getSnapshot = () => this.requests[0] ?? null;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private notify() {
    this.listeners.forEach((listener) => listener());
  }
  show(request: DialogRequest) {
    const current = this.getSession();
    this.requests = this.requests.filter((item) => item.session === current);
    const entry = { ...request, id: ++this.nextId, session: current };
    this.requests.push(entry);
    this.notify();
    return entry.id;
  }
  dismiss = (id: number) => {
    if (this.requests[0]?.id !== id) return;
    this.requests.shift();
    this.notify();
  };
  cancelAll = () => {
    if (!this.requests.length) return;
    this.requests = [];
    this.notify();
  };
  discardExpired = () => {
    const filtered = this.requests.filter(
      (item) => item.session === this.getSession(),
    );
    if (filtered.length === this.requests.length) return;
    this.requests = filtered;
    this.notify();
  };
  confirm = (id: number) => {
    const request = this.requests[0];
    if (!request || request.id !== id) return;
    // Remove synchronously before invoking code: repeated taps cannot execute it twice.
    this.dismiss(id);
    if (request.session !== this.getSession()) {
      this.discardExpired();
      return;
    }
    try {
      Promise.resolve(request.onConfirm?.()).catch(() => this.failure(request));
    } catch {
      this.failure(request);
    }
  };
  private failure(request: QueuedDialog) {
    if (request.session !== this.getSession()) return;
    this.show({
      title: "Não foi possível concluir",
      message:
        "Tente novamente. Se o problema continuar, volte à tela anterior.",
      kind: "information",
    });
  }
}

export function confirmationOptions(title: string): DialogOptions {
  const label = title.replace(/\?+$/, "").trim();
  const destructive = /^(cancelar|remover|excluir|desativar|sair)\b/i.test(
    label,
  );
  return {
    destructive,
    confirmLabel:
      label === "Cliente faltou"
        ? "Registrar falta"
        : label.length <= 30
          ? label
          : "Confirmar",
  };
}
