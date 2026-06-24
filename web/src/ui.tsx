import { useRef, useState } from "react";

type Kind = "error" | "info" | "success";
type ToastItem = { id: number; msg: string; kind: Kind };
type Pending = {
  msg: string;
  ok: string;
  cancel: string;
  resolve: (v: boolean) => void;
};

// мост между императивными вызовами (toast/confirmDialog) и смонтированным UiHost
let pushToast: ((msg: string, kind: Kind) => void) | null = null;
let openConfirm: ((p: Omit<Pending, "resolve">) => Promise<boolean>) | null = null;

export function toast(msg: string, kind: Kind = "info"): void {
  if (pushToast) pushToast(msg, kind);
}

export function confirmDialog(
  msg: string,
  ok = "Подтвердить",
  cancel = "Отмена",
): Promise<boolean> {
  if (openConfirm) return openConfirm({ msg, ok, cancel });
  return Promise.resolve(window.confirm(msg)); // фолбэк, если хост не смонтирован
}

export function UiHost() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [pending, setPending] = useState<Pending | null>(null);
  const seq = useRef(1);

  // регистрируем мост сразу при рендере (не в useEffect) — чтобы к первому клику
  // toast/confirmDialog точно работали и не было отката на нативный confirm
  pushToast = (msg, kind) => {
    const id = seq.current++;
    setToasts((t) => [...t, { id, msg, kind }]);
    const ttl = kind === "error" ? 9000 : 5000;
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), ttl);
  };
  openConfirm = (p) =>
    new Promise<boolean>((resolve) => setPending({ ...p, resolve }));

  function decide(v: boolean) {
    pending?.resolve(v);
    setPending(null);
  }

  return (
    <>
      <div className="toast-wrap">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`toast ${t.kind}`}
            title="скрыть"
            onClick={() => setToasts((x) => x.filter((i) => i.id !== t.id))}
          >
            {t.msg}
          </div>
        ))}
      </div>

      {pending && (
        <div className="modal-backdrop" onClick={() => decide(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                fontSize: 14,
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                marginBottom: 16,
              }}
            >
              {pending.msg}
            </div>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => decide(false)}>
                {pending.cancel}
              </button>
              <button className="btn btn-primary" onClick={() => decide(true)}>
                {pending.ok}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
