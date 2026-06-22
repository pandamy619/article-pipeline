import { type CSSProperties, Fragment, useEffect, useState } from "react";
import {
  addFeed,
  AuthError,
  bulkAction,
  type ChatMsg,
  chatArticle,
  checkAuth,
  clearToken,
  collect,
  createChannel,
  deleteChannel,
  deleteFeed,
  fetchArticles,
  fetchChannels,
  fetchFeeds,
  fetchLastRun,
  fetchSettings,
  fetchStats,
  getToken,
  runAction,
  savePost,
  saveSetting,
  scheduleArticle,
  type SearchResponse,
  searchArticles,
  setArticleStatus,
  setToken,
  unscheduleArticle,
  updateChannel,
} from "./api";
import type { Article, Channel, Feed, LastRun, Stats } from "./types";

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
type View = "articles" | "queue" | "search" | "channels" | "feeds" | "settings";
const NAV: { key: View; label: string }[] = [
  { key: "articles", label: "Статьи" },
  { key: "queue", label: "Очередь" },
  { key: "search", label: "Поиск" },
  { key: "channels", label: "Каналы" },
  { key: "feeds", label: "Ленты" },
  { key: "settings", label: "Настройки" },
];
const VIEW_TITLES: Record<View, string> = {
  articles: "Статьи",
  queue: "Очередь",
  search: "Поиск",
  channels: "Каналы",
  feeds: "Ленты",
  settings: "Настройки",
};

export default function App() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [lastRun, setLastRun] = useState<LastRun | null>(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>("preview");
  const [view, setView] = useState<View>("articles");
  const [needLogin, setNeedLogin] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [channels, setChannels] = useState<Channel[]>([]);
  const [currentChannel, setCurrentChannel] = useState<number | null>(null);

  async function loadChannels() {
    try {
      setChannels(await fetchChannels());
    } catch (e) {
      if (e instanceof AuthError) setNeedLogin(true);
    }
  }

  async function refresh(current: string, channel: number | null) {
    try {
      const [a, s, lr] = await Promise.all([
        fetchArticles(current || undefined, channel),
        fetchStats(channel),
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
    loadChannels();
  }, []);

  useEffect(() => {
    setSelected(new Set());
    refresh(filter, currentChannel);
  }, [filter, currentChannel]);

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
      await refresh(filter, currentChannel);
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
          refresh(filter, currentChannel);
        }}
      />
    );
  }

  // в очереди — показываем по времени публикации (ближайшие сверху)
  const rows =
    filter === "scheduled"
      ? [...articles].sort((a, b) =>
          (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? ""),
        )
      : articles;

  return (
    <div className="shell">
      {busy && <div className="working-badge">работаю…</div>}

      <aside className="sidebar">
        <div className="brand">article-pipeline</div>
        {NAV.map((n) => (
          <button
            key={n.key}
            className={`nav-item${view === n.key ? " active" : ""}`}
            onClick={() => {
              setView(n.key);
              if (n.key === "queue") setFilter("scheduled");
              if (n.key === "articles") setFilter("");
            }}
          >
            {n.label}
          </button>
        ))}
        <div className="sidebar-spacer" />
        <div className="sidebar-foot">
          <select
            value={currentChannel ?? ""}
            onChange={(e) =>
              setCurrentChannel(e.target.value ? Number(e.target.value) : null)
            }
            title="канал"
            style={{
              border: "1px solid var(--line-strong)",
              borderRadius: 8,
              padding: "7px 10px",
              fontSize: 13,
              background: "var(--card)",
              color: "var(--text)",
              fontFamily: "inherit",
            }}
          >
            <option value="">Все каналы</option>
            {channels.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name || `#${c.id}`}
              </option>
            ))}
          </select>
          {getToken() && (
            <button
              className="btn"
              onClick={() => {
                clearToken();
                setNeedLogin(true);
              }}
            >
              Выйти
            </button>
          )}
        </div>
      </aside>

      <main className="main">
        <header className="main-head">
          <h1>{VIEW_TITLES[view]}</h1>
          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={() => run(() => collect())}
          >
            {busy ? "…" : "Собрать сейчас"}
          </button>
        </header>

      {view === "feeds" && <FeedsPanel />}
      {view === "settings" && <SettingsPanel />}
      {view === "channels" && (
        <ChannelsPanel
          channels={channels}
          onChanged={async () => {
            await loadChannels();
            await refresh(filter, currentChannel);
          }}
        />
      )}
      {view === "search" && (
        <SearchPanel
          channel={currentChannel}
          onChanged={() => refresh(filter, currentChannel)}
        />
      )}

      {(view === "articles" || view === "queue") && (
        <>
          {lastRun?.exists && <LastRunLine run={lastRun} />}

          <div className="metrics">
            <div className="metric">
              <div className="v">{stats.total ?? 0}</div>
              <div className="k">всего</div>
            </div>
            {(["new", "drafted", "scheduled", "published"] as const).map((k) => (
              <div className="metric" key={k}>
                <div className="v">{stats[k] ?? 0}</div>
                <div className="k">{STATUS_RU[k]}</div>
              </div>
            ))}
          </div>

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
              <th style={{ width: 270 }}>действия</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
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
                        в очереди на {new Date(a.scheduled_at).toLocaleString()}
                      </div>
                    )}
                  </td>
                  <td className="muted">{a.source}</td>
                  <td>
                    <div className="actions">
                      {a.post_text ? (
                        <>
                          <button
                            className={`alink${
                              openId === a.id && mode === "preview" ? " on" : ""
                            }`}
                            onClick={() => toggle(a.id, "preview")}
                          >
                            превью
                          </button>
                          <button
                            className={`alink${
                              openId === a.id && mode === "edit" ? " on" : ""
                            }`}
                            onClick={() => toggle(a.id, "edit")}
                          >
                            правка
                          </button>
                          {a.status !== "published" && (
                            <button
                              className="alink"
                              disabled={busy}
                              onClick={() => {
                                if (confirm("Опубликовать пост в Telegram-канал?")) {
                                  run(() => runAction(a.id, "publish"));
                                }
                              }}
                            >
                              опубликовать
                            </button>
                          )}
                          {a.status !== "published" && (
                            <button
                              className={`alink${
                                openId === a.id && mode === "schedule" ? " on" : ""
                              }`}
                              onClick={() => toggle(a.id, "schedule")}
                            >
                              в очередь
                            </button>
                          )}
                        </>
                      ) : (
                        <button
                          className="alink"
                          disabled={busy}
                          onClick={() => run(() => runAction(a.id, "draft"))}
                        >
                          сделать пост
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
                          onChanged={() => refresh(filter, currentChannel)}
                          onPreview={() => setMode("preview")}
                        />
                      ) : (
                        <SchedulePanel
                          article={a}
                          onChanged={() => refresh(filter, currentChannel)}
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
        </>
      )}
      </main>
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
            Редактировать
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
          content: `ошибка: ${e instanceof Error ? e.message : String(e)}`,
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
            Превью
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
                  вставить в пост
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
            Отправить
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
        Сбой прогона{run.error ? `: ${run.error}` : ""} · {when}
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

function SearchPanel({
  channel,
  onChanged,
}: {
  channel: number | null;
  onChanged: () => void;
}) {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<SearchResponse | null>(null);

  async function go(mode: "semantic" | "web") {
    const q = query.trim();
    if (!q) return;
    setBusy(true);
    setRes(null);
    try {
      const r = await searchArticles(q, mode, channel);
      setRes(r);
      if (mode === "web") onChanged();
    } catch (e) {
      alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ padding: "14px 16px", marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) go("semantic");
          }}
          placeholder="опиши, что искать (напр. туториалы по асинхронному python)"
          style={{
            flex: 1,
            minWidth: 240,
            border: "1px solid var(--line-strong)",
            borderRadius: 9,
            padding: "8px 11px",
            fontSize: 13,
            fontFamily: "inherit",
          }}
        />
        <button
          className="btn"
          disabled={busy || !query.trim()}
          onClick={() => go("semantic")}
        >
          По собранным
        </button>
        <button
          className="btn btn-primary"
          disabled={busy || !query.trim()}
          onClick={() => go("web")}
        >
          Найти в вебе
        </button>
      </div>

      {busy && (
        <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>
          ищу…
        </div>
      )}

      {res?.mode === "web" && (
        <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>
          Добавлено новых: {res.added}. Запросы: {(res.queries ?? []).join(", ")}.
          Появятся в списке как черновики текущего канала.
        </div>
      )}

      {res?.mode === "semantic" &&
        ((res.results ?? []).length === 0 ? (
          <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>
            Ничего похожего (нужны статьи с эмбеддингами — собери и прогони дедуп).
          </div>
        ) : (
          <table className="tbl" style={{ marginTop: 10 }}>
            <tbody>
              {(res.results ?? []).map((r) => (
                <tr className="row" key={r.id}>
                  <td className="score" style={{ width: 52 }}>
                    {r.similarity.toFixed(2)}
                  </td>
                  <td>
                    <a className="title" href={r.url} target="_blank" rel="noreferrer">
                      {r.title}
                    </a>
                  </td>
                  <td className="muted" style={{ width: 130 }}>
                    {STATUS_RU[r.status] ?? r.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}

      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        «По собранным» — семантический поиск среди уже собранного. «Найти в вебе» —
        LLM придумает запросы, SearXNG принесёт новые статьи в текущий канал.
      </div>
    </div>
  );
}

const CHANNEL_FIELDS: {
  key: keyof Channel;
  label: string;
  type: "text" | "int" | "bool" | "area";
}[] = [
  { key: "name", label: "Название", type: "text" },
  { key: "bot_token", label: "Бот-токен", type: "text" },
  { key: "channel_id", label: "Channel ID (@name или -100…)", type: "text" },
  { key: "admin_user_id", label: "Admin user id", type: "text" },
  { key: "topic", label: "Тематика (для фильтра)", type: "area" },
  { key: "enabled", label: "Включён", type: "bool" },
  { key: "relevance_threshold", label: "Порог релевантности (0–10)", type: "int" },
  { key: "publish_interval_minutes", label: "Интервал публикации (мин)", type: "int" },
  { key: "rss_feeds", label: "RSS-ленты (через запятую)", type: "area" },
  { key: "habr_enabled", label: "Habr включён", type: "bool" },
  { key: "habr_hubs", label: "Habr: хабы", type: "text" },
  { key: "arxiv_categories", label: "arXiv: категории", type: "text" },
  { key: "reddit_subreddits", label: "Reddit: сабреддиты", type: "text" },
  { key: "searxng_queries", label: "Веб-поиск: запросы", type: "area" },
];

const EMPTY_CHANNEL: Partial<Channel> = {
  name: "",
  bot_token: "",
  channel_id: "",
  admin_user_id: "",
  topic: "",
  enabled: true,
  relevance_threshold: 7,
  publish_interval_minutes: 120,
  rss_feeds: "",
  habr_enabled: false,
  habr_hubs: "",
  arxiv_categories: "",
  reddit_subreddits: "",
  searxng_queries: "",
};

function ChannelsPanel({
  channels,
  onChanged,
}: {
  channels: Channel[];
  onChanged: () => Promise<void>;
}) {
  const [editId, setEditId] = useState<number | "new">(channels[0]?.id ?? "new");
  const [form, setForm] = useState<Partial<Channel>>(
    channels[0] ? { ...channels[0] } : { ...EMPTY_CHANNEL },
  );
  const [busy, setBusy] = useState(false);

  function pick(id: number | "new") {
    setEditId(id);
    const c = id === "new" ? null : channels.find((x) => x.id === id);
    setForm(c ? { ...c } : { ...EMPTY_CHANNEL });
  }

  async function save() {
    setBusy(true);
    try {
      if (editId === "new") {
        const created = await createChannel(form);
        await onChanged();
        setEditId(created.id);
      } else {
        await updateChannel(editId, form);
        await onChanged();
      }
    } catch (e) {
      alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (editId === "new") return;
    if (!confirm("Удалить канал? Его статьи отвяжутся.")) return;
    setBusy(true);
    try {
      await deleteChannel(editId);
      setEditId("new");
      setForm({ ...EMPTY_CHANNEL });
      await onChanged();
    } catch (e) {
      alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  const inp: CSSProperties = {
    border: "1px solid var(--line-strong)",
    borderRadius: 8,
    padding: "7px 9px",
    fontSize: 13,
    fontFamily: "inherit",
  };

  return (
    <div className="card" style={{ padding: "14px 16px", marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
        {channels.map((c) => (
          <button
            key={c.id}
            className={`chip${editId === c.id ? " active" : ""}`}
            onClick={() => pick(c.id)}
          >
            {c.name || `#${c.id}`}
          </button>
        ))}
        <button
          className={`chip${editId === "new" ? " active" : ""}`}
          onClick={() => pick("new")}
        >
          + новый
        </button>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "10px 16px",
        }}
      >
        {CHANNEL_FIELDS.map((f) => (
          <label
            key={f.key}
            style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}
          >
            <span className="muted">{f.label}</span>
            {f.type === "bool" ? (
              <select
                value={form[f.key] ? "true" : "false"}
                onChange={(e) =>
                  setForm({ ...form, [f.key]: e.target.value === "true" })
                }
                style={inp}
              >
                <option value="true">вкл</option>
                <option value="false">выкл</option>
              </select>
            ) : f.type === "area" ? (
              <textarea
                value={String(form[f.key] ?? "")}
                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                style={{ ...inp, minHeight: 52, resize: "vertical" }}
              />
            ) : (
              <input
                type={f.type === "int" ? "number" : "text"}
                value={String(form[f.key] ?? "")}
                onChange={(e) =>
                  setForm({
                    ...form,
                    [f.key]:
                      f.type === "int" ? Number(e.target.value) : e.target.value,
                  })
                }
                style={inp}
              />
            )}
          </label>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
        <button className="btn btn-primary" disabled={busy} onClick={save}>
          {editId === "new" ? "Создать" : "Сохранить"}
        </button>
        {editId !== "new" && (
          <button className="btn" disabled={busy} onClick={remove}>
            Удалить канал
          </button>
        )}
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        У каждого канала свой бот-токен, тематика и источники. Изменения
        применяются со следующего прогона.
      </div>
    </div>
  );
}

const SETTING_LABELS: Record<string, string> = {
  llm_model: "Модель LLM",
  embed_model: "Модель эмбеддингов",
  channel_topic: "Тематика канала (для фильтра)",
  relevance_threshold: "Порог релевантности (0–10)",
  run_interval_minutes: "Интервал прогона (мин) ⟳",
  publish_interval_minutes: "Интервал публикации (мин) ⟳",
  max_articles_per_run: "Лимит статей за прогон (0 = без)",
  semantic_dedup_enabled: "Семантический дедуп",
  semantic_dedup_threshold: "Порог дедупа (0–1)",
  habr_enabled: "Habr включён",
  habr_hubs: "Habr: хабы через запятую",
  arxiv_categories: "arXiv: категории",
  reddit_subreddits: "Reddit: сабреддиты",
  searxng_queries: "Веб-поиск: запросы",
};

function SettingsPanel() {
  const [types, setTypes] = useState<Record<string, string>>({});
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  async function load() {
    const d = await fetchSettings();
    setTypes(d.types);
    const f: Record<string, string> = {};
    for (const k of Object.keys(d.types)) {
      const v = d.settings[k];
      f[k] = typeof v === "boolean" ? (v ? "true" : "false") : String(v ?? "");
    }
    setForm(f);
  }
  useEffect(() => {
    load();
  }, []);

  async function save() {
    setBusy(true);
    setSaved(false);
    try {
      for (const k of Object.keys(types)) await saveSetting(k, form[k] ?? "");
      setSaved(true);
      await load();
    } catch (e) {
      alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  const inp: CSSProperties = {
    border: "1px solid var(--line-strong)",
    borderRadius: 8,
    padding: "7px 9px",
    fontSize: 13,
    fontFamily: "inherit",
  };

  return (
    <div className="card" style={{ padding: "14px 16px", marginBottom: 16 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "10px 16px",
        }}
      >
        {Object.keys(types).map((k) => (
          <label
            key={k}
            style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}
          >
            <span className="muted">{SETTING_LABELS[k] ?? k}</span>
            {types[k] === "bool" ? (
              <select
                value={form[k] ?? "false"}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                style={inp}
              >
                <option value="true">вкл</option>
                <option value="false">выкл</option>
              </select>
            ) : k === "channel_topic" ? (
              <textarea
                value={form[k] ?? ""}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                style={{ ...inp, minHeight: 60, resize: "vertical" }}
              />
            ) : (
              <input
                type={types[k] === "int" || types[k] === "float" ? "number" : "text"}
                step={types[k] === "float" ? "0.01" : "1"}
                value={form[k] ?? ""}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                style={inp}
              />
            )}
          </label>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12 }}>
        <button className="btn btn-primary" disabled={busy} onClick={save}>
          Сохранить
        </button>
        {saved && (
          <span className="muted" style={{ fontSize: 12 }}>
            сохранено
          </span>
        )}
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Применяется со следующего прогона. Пункты с ⟳ (интервалы) — после
        перезапуска бота.
      </div>
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
              <td style={{ width: 80, textAlign: "right" }}>
                {f.source === "db" && f.id != null && (
                  <button
                    className="act"
                    disabled={busy}
                    onClick={() => wrap(() => deleteFeed(f.id as number))}
                  >
                    удалить
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
