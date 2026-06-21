import { type CSSProperties, Fragment, useEffect, useState } from "react";
import {
  collect,
  fetchArticles,
  fetchStats,
  revisePost,
  runAction,
  savePost,
} from "./api";
import type { Article, Stats } from "./types";

const STATUSES = ["new", "filtered", "drafted", "pending", "published", "rejected"];
type Mode = "preview" | "edit";

export default function App() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>("preview");

  async function refresh(current: string) {
    const [a, s] = await Promise.all([
      fetchArticles(current || undefined),
      fetchStats(),
    ]);
    setArticles(a);
    setStats(s);
  }

  useEffect(() => {
    refresh(status);
  }, [status]);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
      await refresh(status);
    } finally {
      setBusy(false);
    }
  }

  function openPanel(id: number, m: Mode) {
    if (openId === id && mode === m) {
      setOpenId(null);
    } else {
      setOpenId(id);
      setMode(m);
    }
  }

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", margin: 24 }}>
      <h1 style={{ fontSize: 20 }}>article-pipeline — статьи</h1>

      <button disabled={busy} onClick={() => run(() => collect())}>
        🔄 Собрать сейчас
      </button>

      <div style={{ margin: "12px 0" }}>
        <FilterTab
          label={`все (${stats.total ?? 0})`}
          active={status === ""}
          onClick={() => setStatus("")}
        />
        {STATUSES.map((st) => (
          <FilterTab
            key={st}
            label={`${st} (${stats[st] ?? 0})`}
            active={status === st}
            onClick={() => setStatus(st)}
          />
        ))}
      </div>

      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
        <thead>
          <tr>
            {["id", "статус", "оценка", "заголовок / причина", "источник", "действия"].map(
              (h) => (
                <th key={h} style={th}>
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {articles.map((a) => (
            <Fragment key={a.id}>
              <tr>
                <td style={td}>{a.id}</td>
                <td style={td}>
                  <span style={badge(a.status)}>{a.status}</span>
                </td>
                <td style={td}>{a.relevance_score ?? ""}</td>
                <td style={td}>
                  <a href={a.url} target="_blank" rel="noreferrer">
                    {a.title}
                  </a>
                  <br />
                  <small style={{ color: "#666" }}>{a.relevance_reason}</small>
                </td>
                <td style={td}>{a.source}</td>
                <td style={{ ...td, whiteSpace: "nowrap" }}>
                  {a.post_text && (
                    <button onClick={() => openPanel(a.id, "preview")} title="превью">
                      📄
                    </button>
                  )}
                  {a.post_text && (
                    <button onClick={() => openPanel(a.id, "edit")} title="редактировать">
                      ✏️
                    </button>
                  )}
                  <button
                    disabled={busy}
                    title="опубликовать"
                    onClick={() => run(() => runAction(a.id, "publish"))}
                  >
                    ✅
                  </button>
                  <button
                    disabled={busy}
                    title="отклонить"
                    onClick={() => run(() => runAction(a.id, "reject"))}
                  >
                    ❌
                  </button>
                </td>
              </tr>
              {openId === a.id && a.post_text && (
                <tr>
                  <td style={td} colSpan={6}>
                    {mode === "preview" ? (
                      <PreviewPanel text={a.post_text} onEdit={() => setMode("edit")} />
                    ) : (
                      <EditPanel
                        article={a}
                        onChanged={() => refresh(status)}
                        onPreview={() => setMode("preview")}
                      />
                    )}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
          {articles.length === 0 && (
            <tr>
              <td style={td} colSpan={6}>
                пусто
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function PreviewPanel({ text, onEdit }: { text: string; onEdit: () => void }) {
  return (
    <div>
      <button onClick={onEdit} style={{ marginBottom: 8 }}>
        ✏️ Редактировать
      </button>
      <TelegramPreview text={text} />
    </div>
  );
}

function EditPanel({
  article,
  onChanged,
  onPreview,
}: {
  article: Article;
  onChanged: () => Promise<void>;
  onPreview: () => void;
}) {
  const [text, setText] = useState(article.post_text ?? "");
  const [instruction, setInstruction] = useState("");
  const [working, setWorking] = useState(false);
  const [log, setLog] = useState<string[]>([]);

  async function save() {
    setWorking(true);
    try {
      await savePost(article.id, text);
      await onChanged();
    } finally {
      setWorking(false);
    }
  }

  async function ask() {
    const ins = instruction.trim();
    if (!ins) return;
    setWorking(true);
    setLog((l) => [...l, `🧑 ${ins}`]);
    try {
      const updated = await revisePost(article.id, ins);
      if (updated) setText(updated);
      setLog((l) => [...l, "🤖 переписал пост ✓"]);
      setInstruction("");
      await onChanged();
    } finally {
      setWorking(false);
    }
  }

  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
      {/* слева: правка прямо в окне поста */}
      <div style={{ flex: "1 1 380px" }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
          <button onClick={onPreview}>👁 Превью</button>
          <button disabled={working} onClick={save}>
            💾 Сохранить
          </button>
        </div>
        <div style={{ background: "#cfe0ee", padding: 16, borderRadius: 8 }}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{
              width: "100%",
              maxWidth: 480,
              minHeight: 220,
              boxSizing: "border-box",
              background: "#fff",
              border: "none",
              borderRadius: 12,
              padding: "8px 12px",
              fontFamily: "inherit",
              fontSize: 15,
              lineHeight: 1.45,
              resize: "vertical",
              boxShadow: "0 1px 1px rgba(0,0,0,0.15)",
            }}
          />
        </div>
      </div>

      {/* справа: чат с моделью */}
      <div
        style={{
          flex: "1 1 300px",
          display: "flex",
          flexDirection: "column",
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 10,
        }}
      >
        <strong style={{ fontSize: 13 }}>Чат с ИИ</strong>
        <div
          style={{
            flex: 1,
            minHeight: 140,
            maxHeight: 220,
            overflowY: "auto",
            fontSize: 13,
            color: "#444",
            margin: "8px 0",
          }}
        >
          {log.length === 0 ? (
            <span style={{ color: "#999" }}>
              Опиши, что изменить — модель перепишет пост слева.
            </span>
          ) : (
            log.map((line, i) => (
              <div key={i} style={{ marginBottom: 4 }}>
                {line}
              </div>
            ))
          )}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <input
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") ask();
            }}
            placeholder="сделай короче, добавь эмодзи…"
            style={{ flex: 1, padding: 6 }}
          />
          <button disabled={working} onClick={ask}>
            ➤
          </button>
        </div>
        {working && <small style={{ color: "#666" }}>модель думает…</small>}
      </div>
    </div>
  );
}

function linkify(text: string) {
  return text.split(/(https?:\/\/\S+|#[\wа-яёА-ЯЁ]+)/g).map((part, i) => {
    if (/^https?:\/\//.test(part)) {
      return (
        <a key={i} href={part} target="_blank" rel="noreferrer" style={{ color: "#2481cc" }}>
          {part}
        </a>
      );
    }
    if (/^#/.test(part)) {
      return (
        <span key={i} style={{ color: "#2481cc" }}>
          {part}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function TelegramPreview({ text }: { text: string }) {
  return (
    <div style={{ background: "#cfe0ee", padding: 16, borderRadius: 8 }}>
      <div
        style={{
          background: "#fff",
          maxWidth: 480,
          padding: "8px 12px",
          borderRadius: 12,
          fontSize: 15,
          lineHeight: 1.45,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          boxShadow: "0 1px 1px rgba(0,0,0,0.15)",
        }}
      >
        {linkify(text)}
      </div>
    </div>
  );
}

function FilterTab(props: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={props.onClick}
      style={{
        marginRight: 8,
        background: props.active ? "#2563eb" : "#eee",
        color: props.active ? "#fff" : "#111",
        border: "none",
        borderRadius: 4,
        padding: "4px 8px",
        cursor: "pointer",
      }}
    >
      {props.label}
    </button>
  );
}

const th: CSSProperties = {
  border: "1px solid #ddd",
  padding: "6px 8px",
  textAlign: "left",
  background: "#f5f5f5",
};
const td: CSSProperties = {
  border: "1px solid #ddd",
  padding: "6px 8px",
  textAlign: "left",
  verticalAlign: "top",
};

const COLORS: Record<string, string> = {
  new: "#eee",
  filtered: "#dbeafe",
  drafted: "#fde68a",
  pending: "#fed7aa",
  published: "#bbf7d0",
  rejected: "#fecaca",
};

function badge(status: string): CSSProperties {
  return {
    background: COLORS[status] ?? "#eee",
    padding: "2px 6px",
    borderRadius: 4,
    fontSize: 12,
  };
}
