import { Fragment, useEffect, useState } from "react";
import {
  addFeed,
  AuthError,
  bulkAction,
  type ChatMsg,
  chatArticle,
  checkAuth,
  clearToken,
  collect,
  deleteFeed,
  fetchArticles,
  fetchFeeds,
  getToken,
  fetchLastRun,
  fetchStats,
  runAction,
  savePost,
  scheduleArticle,
  setArticleStatus,
  setToken,
  unscheduleArticle,
} from "./api";
import type { Article, Feed, LastRun, Stats } from "./types";

const STATUSES = [
  "new",
  "filtered",
  "drafted",
  "pending",
  "scheduled",
  "published",
  "rejected",
];
const STATUS_RU: Record<string, string> = {
  new: "новая",
  filtered: "прошла фильтр",
  drafted: "черновик",
  pending: "на модерации",
  scheduled: "в очереди",
  published: "опубликована",
  rejected: "отклонена",
};
type Mode = "preview" | "edit" | "schedule";

export default function App() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [lastRun, setLastRun] = useState<LastRun | null>(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>("preview");
  const [showFeeds, setShowFeeds] = useState(false);
  const [needLogin, setNeedLogin] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  async function refresh(current: string) {
    try {
      const [a, s, lr] = await Promise.all([
        fetchArticles(current || undefined),
        fetchStats(),
        fetchLastRun(),
      ]);
      setArticles(a);
      setStats(s);
      setLastRun(lr);
    } catch (e) {
      if (e instanceof AuthError) setNeedLogin(true);
      else throw e;
    }
  }

  useEffect(() => {
    setSelected(new Set());
    refresh(filter);
  }, [filter]);

  function toggleSel(id: number) {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  function runBulk(action: string) {
    const ids = [...selected];
    if (!ids.length) return;
    run(async () => {
      await bulkAction(ids, action);
      setSelected(new Set());
    });
  }

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
      await refresh(filter);
    } catch (e) {
      if (e instanceof AuthError) setNeedLogin(true);
      else alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: number, m: Mode) {
    if (openId === id && mode === m) setOpenId(null);
    else {
      setOpenId(id);
      setMode(m);
    }
  }

  if (needLogin) {
    return (
      <Login
        onSuccess={() => {
          setNeedLogin(false);
          refresh(filter);
        }}
      />
    );
  }

  return (
    <div className="app">
      {busy && <div className="working-badge">работаю…</div>}

      <header className="topbar">
        <div>
          <h1>article-pipeline</h1>
          <p className="sub">панель модерации статей</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => setShowFeeds((v) => !v)}>
            Ленты
          </button>
          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={() => run(() => collect())}
          >
            {busy ? "…" : "Собрать сейчас"}
          </button>
          {getToken() && (
            <button
              className="btn"
              title="выйти"
              onClick={() => {
                clearToken();
                setNeedLogin(true);
              }}
            >
              Выйти
            </button>
          )}
        </div>
      </header>

      {showFeeds && <FeedsPanel />}

      {lastRun?.exists && <LastRunLine run={lastRun} />}

      {selected.size > 0 && (
        <div
          className="card"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 14px",
            marginBottom: 12,
            flexWrap: "wrap",
          }}
        >
          <span style={{ fontWeight: 500 }}>Выбрано {selected.size}</span>
          <button className="btn" disabled={busy} onClick={() => runBulk("queue")}>
            В очередь
          </button>
          <button className="btn" disabled={busy} onClick={() => runBulk("unqueue")}>
            Снять с очереди
          </button>
          <button className="btn" disabled={busy} onClick={() => runBulk("reject")}>
            Отклонить
          </button>
          <button
            className="btn"
            disabled={busy}
            onClick={() => {
              if (confirm(`Опубликовать ${selected.size} статей в канал сейчас?`)) {
                runBulk("publish");
              }
            }}
          >
            Опубликовать
          </button>
          <button
            className="btn"
            style={{ marginLeft: "auto" }}
            onClick={() => setSelected(new Set())}
          >
            Снять выделение
          </button>
        </div>
      )}

      <nav className="chips">
        <button
          className={`chip${filter === "" ? " active" : ""}`}
          onClick={() => setFilter("")}
        >
          все <b>{stats.total ?? 0}</b>
        </button>
        {STATUSES.map((s) => (
          <button
            key={s}
            className={`chip${filter === s ? " active" : ""}`}
            onClick={() => setFilter(s)}
          >
            {STATUS_RU[s]} <b>{stats[s] ?? 0}</b>
          </button>
        ))}
      </nav>

      <div className="card">
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 30 }}>
                <input
                  type="checkbox"
                  checked={articles.length > 0 && selected.size === articles.length}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? new Set(articles.map((a) => a.id))
                        : new Set(),
                    )
                  }
                />
              </th>
              <th style={{ width: 36 }}>#</th>
              <th style={{ width: 158 }}>статус</th>
              <th style={{ width: 56 }}>оценка</th>
              <th>заголовок и причина</th>
              <th style={{ width: 100 }}>источник</th>
              <th style={{ width: 132 }}>действия</th>
            </tr>
          </thead>
          <tbody>
            {articles.map((a) => (
              <Fragment key={a.id}>
                <tr className="row">
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(a.id)}
                      onChange={() => toggleSel(a.id)}
                    />
                  </td>
                  <td className="muted">{a.id}</td>
                  <td>
                    <select
                      className={`select st-${a.status}`}
                      value={a.status}
                      disabled={busy || a.status === "published"}
                      title={
                        a.status === "published"
                          ? "опубликованную статью менять нельзя"
                          : "сменить статус вручную"
                      }
                      onChange={(e) => run(() => setArticleStatus(a.id, e.target.value))}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {STATUS_RU[s]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    {a.relevance_score != null ? (
                      <span className="score">{a.relevance_score}</span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td>
                    <a className="title" href={a.url} target="_blank" rel="noreferrer">
                      {a.title}
                    </a>
                    {a.relevance_reason && <div className="reason">{a.relevance_reason}</div>}
                    {a.status === "scheduled" && a.scheduled_at && (
                      <div className="reason">
                        🕒 в очереди на {new Date(a.scheduled_at).toLocaleString()}
                      </div>
                    )}
                  </td>
                  <td className="muted">{a.source}</td>
                  <td>
                    <div className="actions">
                      {a.post_text ? (
                        <>
                          <button
                            className={`icon${
                              openId === a.id && mode === "preview" ? " on" : ""
                            }`}
                            title="превью"
                            onClick={() => toggle(a.id, "preview")}
                          >
                            👁
                          </button>
                          <button
                            className={`icon${
                              openId === a.id && mode === "edit" ? " on" : ""
                            }`}
                            title="редактировать"
                            onClick={() => toggle(a.id, "edit")}
                          >
                            ✏️
                          </button>
                          {a.status !== "published" && (
                            <button
                              className="icon"
                              title="опубликовать в канал"
                              disabled={busy}
                              onClick={() => {
                                if (confirm("Опубликовать пост в Telegram-канал?")) {
                                  run(() => runAction(a.id, "publish"));
                                }
                              }}
                            >
                              🚀
                            </button>
                          )}
                          {a.status !== "published" && (
                            <button
                              className={`icon${
                                openId === a.id && mode === "schedule" ? " on" : ""
                              }`}
                              title="запланировать публикацию"
                              onClick={() => toggle(a.id, "schedule")}
                            >
                              ⏰
                            </button>
                          )}
                        </>
                      ) : (
                        <button
                          className="icon"
                          title="сгенерировать пост"
                          disabled={busy}
                          onClick={() => run(() => runAction(a.id, "draft"))}
                        >
                          ✍️
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {openId === a.id && a.post_text && (
                  <tr>
                    <td colSpan={7} className="panel-cell">
                      {mode === "preview" ? (
                        <PreviewPanel
                          text={a.post_text}
                          image={a.image_url}
                          onEdit={() => setMode("edit")}
                        />
                      ) : mode === "edit" ? (
                        <EditPanel
                          article={a}
                          onChanged={() => refresh(filter)}
                          onPreview={() => setMode("preview")}
                        />
                      ) : (
                        <SchedulePanel
                          article={a}
                          onChanged={() => refresh(filter)}
                        />
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {articles.length === 0 && (
              <tr>
                <td colSpan={7}>
                  <div className="empty">Здесь пока пусто</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Login({ onSuccess }: { onSuccess: () => void }) {
  const [token, setTok] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setErr("");
    try {
      if (await checkAuth(token.trim())) {
        setToken(token.trim());
        onSuccess();
      } else {
        setErr("Неверный токен");
      }
    } catch {
      setErr("Ошибка сети");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <div
        className="card"
        style={{ maxWidth: 360, margin: "64px auto", padding: "24px 22px" }}
      >
        <h1 style={{ margin: "0 0 4px" }}>Вход в админку</h1>
        <p className="sub" style={{ marginBottom: 16 }}>
          Введите токен (ADMIN_TOKEN из .env)
        </p>
        <input
          type="password"
          value={token}
          onChange={(e) => setTok(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && token.trim()) submit();
          }}
          placeholder="токен"
          style={{
            width: "100%",
            border: "1px solid var(--line-strong)",
            borderRadius: 9,
            padding: "9px 11px",
            fontSize: 14,
            marginBottom: 10,
          }}
        />
        {err && (
          <div style={{ color: "#c02626", fontSize: 13, marginBottom: 10 }}>{err}</div>
        )}
        <button
          className="btn btn-primary"
          disabled={busy || !token.trim()}
          onClick={submit}
          style={{ width: "100%" }}
        >
          Войти
        </button>
      </div>
    </div>
  );
}

function PreviewPanel({
  text,
  image,
  onEdit,
}: {
  text: string;
  image: string | null;
  onEdit: () => void;
}) {
  return (
    <div className="panel">
      <div className="col">
        <div className="toolbar">
          <button className="btn" onClick={onEdit}>
            ✏️ Редактировать
          </button>
        </div>
        <TelegramView text={text} image={image} />
      </div>
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
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [working, setWorking] = useState(false);

  async function save() {
    setWorking(true);
    try {
      await savePost(article.id, text);
      await onChanged();
    } catch (e) {
      alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setWorking(false);
    }
  }

  async function send() {
    const msg = input.trim();
    if (!msg) return;
    const next: ChatMsg[] = [...messages, { role: "user", content: msg }];
    setMessages(next);
    setInput("");
    setWorking(true);
    try {
      const reply = await chatArticle(article.id, next);
      setMessages([...next, { role: "assistant", content: reply }]);
    } catch (e) {
      setMessages([
        ...next,
        {
          role: "assistant",
          content: `⚠️ ошибка: ${e instanceof Error ? e.message : String(e)}`,
        },
      ]);
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="panel">
      <div className="col">
        <div className="toolbar">
          <button className="btn" onClick={onPreview}>
            👁 Превью
          </button>
          <button className="btn btn-primary" disabled={working} onClick={save}>
            Сохранить
          </button>
        </div>
        <div className="tg-wrap">
          <textarea
            className="tg-edit"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
      </div>

      <div className="chat">
        <div className="chat-title">Чат с ИИ по статье</div>
        <div className="chat-log">
          {messages.length === 0 && (
            <span className="hint">Спроси по статье или попроси переписать пост.</span>
          )}
          {messages.map((m, i) => (
            <Fragment key={i}>
              <div className={`msg ${m.role}`}>{m.content}</div>
              {m.role === "assistant" && (
                <button className="msg-apply" onClick={() => setText(m.content)}>
                  ↧ вставить в пост
                </button>
              )}
            </Fragment>
          ))}
          {working && <span className="hint">модель печатает…</span>}
        </div>
        <div className="chat-input">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") send();
            }}
            placeholder="напиши сообщение…"
          />
          <button className="btn btn-primary" disabled={working} onClick={send}>
            ➤
          </button>
        </div>
      </div>
    </div>
  );
}

function linkify(text: string) {
  return text.split(/(https?:\/\/\S+|#[\wа-яёА-ЯЁ]+)/g).map((part, i) => {
    if (/^https?:\/\//.test(part)) {
      return (
        <a key={i} className="tg-link" href={part} target="_blank" rel="noreferrer">
          {part}
        </a>
      );
    }
    if (/^#/.test(part)) {
      return (
        <span key={i} className="tg-link">
          {part}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

function SchedulePanel({
  article,
  onChanged,
}: {
  article: Article;
  onChanged: () => Promise<void>;
}) {
  const [when, setWhen] = useState(toLocalInput(article.scheduled_at));
  const [busy, setBusy] = useState(false);

  async function wrap(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
      await onChanged();
    } catch (e) {
      alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <div className="col" style={{ maxWidth: 460 }}>
        <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
          {article.status === "scheduled" && article.scheduled_at
            ? `В очереди на ${new Date(article.scheduled_at).toLocaleString()}`
            : "Не в очереди"}
        </div>
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            flexWrap: "wrap",
            marginBottom: 10,
          }}
        >
          <input
            type="datetime-local"
            value={when}
            onChange={(e) => setWhen(e.target.value)}
            style={{
              border: "1px solid var(--line-strong)",
              borderRadius: 9,
              padding: "7px 10px",
              fontSize: 13,
              fontFamily: "inherit",
            }}
          />
          <button
            className="btn"
            disabled={busy || !when}
            onClick={() =>
              wrap(() => scheduleArticle(article.id, new Date(when).toISOString()))
            }
          >
            Запланировать на это время
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={() => wrap(() => scheduleArticle(article.id, null))}
          >
            В очередь (авто, +интервал)
          </button>
          {article.status === "scheduled" && (
            <button
              className="btn"
              disabled={busy}
              onClick={() => wrap(() => unscheduleArticle(article.id))}
            >
              Убрать из очереди
            </button>
          )}
        </div>
        <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>
          «Авто» ставит в конец очереди с шагом PUBLISH_INTERVAL_MINUTES. Публикует
          фоновый планировщик по времени.
        </div>
      </div>
    </div>
  );
}

function LastRunLine({ run }: { run: LastRun }) {
  const when = run.created_at ? new Date(run.created_at).toLocaleString() : "";
  if (run.ok === false) {
    return (
      <div style={{ fontSize: 12, marginBottom: 12, color: "#c02626" }}>
        ⚠️ последний прогон упал{run.error ? `: ${run.error}` : ""} · {when}
      </div>
    );
  }
  const dups = (run.duplicates ?? 0) + (run.semantic_duplicates ?? 0);
  return (
    <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
      последний прогон: собрано {run.collected}, добавлено {run.added}, дублей {dups},
      в фильтр {run.filtered}, черновиков {run.drafted} · {when}
    </div>
  );
}

function FeedsPanel() {
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setFeeds(await fetchFeeds());
  }
  useEffect(() => {
    load();
  }, []);

  async function wrap(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (e) {
      alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ padding: "14px 16px", marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 7, marginBottom: 12 }}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            const u = url.trim();
            if (!u) return;
            setUrl("");
            wrap(() => addFeed(u));
          }}
          placeholder="https://сайт/feed — добавить RSS-ленту"
          style={{
            flex: 1,
            border: "1px solid var(--line-strong)",
            borderRadius: 9,
            padding: "8px 11px",
            fontSize: 13,
            fontFamily: "inherit",
          }}
        />
        <button
          className="btn btn-primary"
          disabled={busy || !url.trim()}
          onClick={() => {
            const u = url.trim();
            setUrl("");
            wrap(() => addFeed(u));
          }}
        >
          Добавить
        </button>
      </div>
      <table className="tbl">
        <tbody>
          {feeds.map((f, i) => (
            <tr className="row" key={i}>
              <td className="muted" style={{ width: 56 }}>
                {f.source === "env" ? "env" : `#${f.id}`}
              </td>
              <td>
                <a className="title" href={f.url} target="_blank" rel="noreferrer">
                  {f.url}
                </a>
              </td>
              <td style={{ width: 40, textAlign: "right" }}>
                {f.source === "db" && f.id != null && (
                  <button
                    className="icon"
                    title="удалить ленту"
                    disabled={busy}
                    onClick={() => wrap(() => deleteFeed(f.id as number))}
                  >
                    🗑
                  </button>
                )}
              </td>
            </tr>
          ))}
          {feeds.length === 0 && (
            <tr>
              <td className="muted">Лент пока нет</td>
            </tr>
          )}
        </tbody>
      </table>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Ленты <b>env</b> задаются в .env и здесь не удаляются. Добавленные тут
        применяются со следующего сбора.
      </div>
    </div>
  );
}

function TelegramView({ text, image }: { text: string; image?: string | null }) {
  return (
    <div className="tg-wrap">
      <div className="tg-bubble">
        {image && <img className="tg-photo" src={image} alt="" />}
        {linkify(text)}
      </div>
    </div>
  );
}
