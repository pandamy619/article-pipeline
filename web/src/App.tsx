import { type CSSProperties, Fragment, useEffect, useState } from "react";
import { collect, fetchArticles, fetchStats, runAction } from "./api";
import type { Article, Stats } from "./types";

const STATUSES = ["new", "filtered", "drafted", "pending", "published", "rejected"];

export default function App() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);

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
                    <button
                      onClick={() => setOpenId(openId === a.id ? null : a.id)}
                      title="превью поста"
                    >
                      📄
                    </button>
                  )}
                  <button disabled={busy} onClick={() => run(() => runAction(a.id, "draft"))}>
                    ✍
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => run(() => runAction(a.id, "publish"))}
                  >
                    ✅
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => run(() => runAction(a.id, "reject"))}
                  >
                    ❌
                  </button>
                </td>
              </tr>
              {openId === a.id && a.post_text && (
                <tr>
                  <td style={td} colSpan={6}>
                    <pre
                      style={{
                        whiteSpace: "pre-wrap",
                        margin: 0,
                        fontFamily: "inherit",
                        background: "#f9fafb",
                        padding: 8,
                        borderRadius: 4,
                      }}
                    >
                      {a.post_text}
                    </pre>
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
