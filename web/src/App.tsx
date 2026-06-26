import {
  type ChangeEvent,
  type CSSProperties,
  Fragment,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  addFeed,
  approveArticle,
  AuthError,
  bulkAction,
  type ChatMsg,
  chatArticle,
  checkAuth,
  clearImage,
  clearToken,
  collect,
  collectActive,
  collectStatus,
  createChannel,
  deleteChannel,
  deleteFeed,
  fetchArticles,
  fetchChannels,
  fetchFeeds,
  fetchLastRun,
  fetchPendingWeb,
  fetchSettings,
  fetchStats,
  getToken,
  runAction,
  savePost,
  saveSetting,
  scheduleArticle,
  searchArticles,
  setArticleStatus,
  setToken,
  unscheduleArticle,
  updateChannel,
  uploadImage,
} from "./api";
import type { Article, Channel, CollectJob, Feed, LastRun, Stats } from "./types";
import { confirmDialog, toast } from "./ui";

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
  { key: "feeds", label: "Ленты" },
  { key: "settings", label: "Настройки" },
  { key: "channels", label: "Проекты" },
];
const VIEW_TITLES: Record<View, string> = {
  articles: "Статьи",
  queue: "Очередь",
  search: "Поиск",
  channels: "Проекты",
  feeds: "Ленты",
  settings: "Настройки",
};

type SortKey = "id" | "status" | "score" | "source";
type Sort = { key: SortKey; dir: "asc" | "desc" };

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
  const [sort, setSort] = useState<Sort>({ key: "id", dir: "desc" });
  const [collectJob, setCollectJob] = useState<CollectJob | null>(null);

  const collecting =
    collectJob?.status === "queued" || collectJob?.status === "running";
  const collectNote = !collectJob
    ? ""
    : collectJob.status === "queued"
      ? "сбор в очереди…"
      : collectJob.status === "running"
        ? "идёт сбор…"
        : collectJob.status === "done"
          ? `готово: +${collectJob.result?.added ?? 0}, черновиков ${collectJob.result?.drafted ?? 0}`
          : "сбор упал";

  async function startCollect() {
    try {
      const job = await collect(currentChannel);
      setCollectJob(job);
    } catch (e) {
      if (e instanceof AuthError) setNeedLogin(true);
      else
        toast(
          `Не удалось запустить сбор: ${e instanceof Error ? e.message : String(e)}`,
          "error",
        );
    }
  }

  async function loadChannels() {
    try {
      const cs = await fetchChannels();
      setChannels(cs);
      setCurrentChannel((cur) => cur ?? cs[0]?.id ?? null);
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

  // авто-обновление: тихо подтягиваем свежие данные каждые 15с (если не заняты)
  useEffect(() => {
    const id = setInterval(() => {
      if (!busy && !needLogin) refresh(filter, currentChannel);
    }, 15000);
    return () => clearInterval(id);
  }, [filter, currentChannel, busy, needLogin]);

  // при загрузке восстанавливаем активную задачу сбора (переживает перезагрузку)
  useEffect(() => {
    collectActive()
      .then((jobs) => {
        if (jobs.length) setCollectJob(jobs[0]);
      })
      .catch(() => {});
  }, []);

  // пока задача сбора активна — опрашиваем её статус и по готовности обновляем
  useEffect(() => {
    if (!collectJob) return;
    if (collectJob.status !== "queued" && collectJob.status !== "running") return;
    const jobId = collectJob.id;
    let stop = false;
    const id = setInterval(async () => {
      try {
        const j = await collectStatus(jobId);
        if (stop) return;
        setCollectJob(j);
        if (j.status === "done" || j.status === "error") {
          await refresh(filter, currentChannel);
          if (j.status === "error") toast(`Сбор упал: ${j.error ?? ""}`, "error");
          setTimeout(
            () => setCollectJob((c) => (c && c.id === j.id ? null : c)),
            7000,
          );
        }
      } catch (e) {
        if (e instanceof AuthError) setNeedLogin(true);
      }
    }, 2500);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, [collectJob?.id, collectJob?.status, filter, currentChannel]);

  function toggleSort(key: SortKey) {
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key, dir: key === "id" || key === "score" ? "desc" : "asc" },
    );
  }

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
      else toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
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

  // в очереди — по времени публикации; иначе — по выбранной колонке
  const rows = [...articles].sort((a, b) => {
    if (filter === "scheduled") {
      return (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? "");
    }
    const dir = sort.dir === "asc" ? 1 : -1;
    let cmp = 0;
    if (sort.key === "score") {
      cmp = (a.relevance_score ?? -1) - (b.relevance_score ?? -1);
    } else if (sort.key === "status") {
      cmp = a.status.localeCompare(b.status);
    } else if (sort.key === "source") {
      cmp = (a.source ?? "").localeCompare(b.source ?? "");
    } else {
      cmp = a.id - b.id;
    }
    return dir * cmp;
  });
  const caret = (k: SortKey) =>
    sort.key === k ? (sort.dir === "asc" ? " ↑" : " ↓") : "";
  const channelName = (id: number) =>
    channels.find((c) => c.id === id)?.name || `проект #${id}`;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">article-pipeline</div>

        <div className="project-switch">
          <span className="project-label">Проект</span>
          <select
            className="project-select"
            value={currentChannel ?? ""}
            onChange={(e) =>
              setCurrentChannel(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">Все проекты</option>
            {channels.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name || `проект #${c.id}`}
              </option>
            ))}
          </select>
        </div>

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
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <h1>{VIEW_TITLES[view]}</h1>
            {busy && (
              <span className="muted" style={{ fontSize: 13 }}>
                обновляю…
              </span>
            )}
            {collectNote && (
              <span
                className="muted"
                style={{
                  fontSize: 13,
                  color: collectJob?.status === "error" ? "#c02626" : undefined,
                }}
              >
                {collectNote}
              </span>
            )}
          </div>
          {view !== "search" && (
            <button
              className="btn btn-primary"
              disabled={busy || collecting}
              style={{ minWidth: 152 }}
              onClick={startCollect}
            >
              {collecting ? "Собираю…" : "Собрать сейчас"}
            </button>
          )}
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
            onClick={async () => {
              if (
                await confirmDialog(
                  `Опубликовать ${selected.size} статей в канал сейчас?`,
                  "Опубликовать",
                )
              ) {
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
              <th
                style={{ width: 36, cursor: "pointer" }}
                onClick={() => toggleSort("id")}
              >
                #{caret("id")}
              </th>
              <th
                style={{ width: 158, cursor: "pointer" }}
                onClick={() => toggleSort("status")}
              >
                статус{caret("status")}
              </th>
              <th
                style={{ width: 56, cursor: "pointer" }}
                onClick={() => toggleSort("score")}
              >
                оценка{caret("score")}
              </th>
              <th>заголовок и причина</th>
              <th
                style={{ width: 100, cursor: "pointer" }}
                onClick={() => toggleSort("source")}
              >
                источник{caret("source")}
              </th>
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
                    {currentChannel === null && a.channel_id != null && (
                      <div className="reason">проект: {channelName(a.channel_id)}</div>
                    )}
                  </td>
                  <td className="muted">{a.source}</td>
                  <td>
                    <div className="actions">
                      {(() => {
                        // единственный замок — статус: отклонена/занят гасят всё.
                        // Иначе кнопки доступны; панели работают и без готового поста.
                        const locked = busy || a.status === "rejected";
                        const hasPost = !!a.post_text;
                        const published = a.status === "published";
                        return (
                          <>
                            <button
                              className="alink"
                              disabled={locked || published || hasPost}
                              title={
                                a.status === "rejected"
                                  ? "сначала смените статус"
                                  : hasPost
                                    ? "пост уже создан — правьте в «правка»"
                                    : "сгенерировать пост ИИ"
                              }
                              onClick={() => run(() => runAction(a.id, "draft"))}
                            >
                              сделать пост
                            </button>
                            <button
                              className={`alink${
                                openId === a.id && mode === "preview" ? " on" : ""
                              }`}
                              disabled={locked}
                              onClick={() => toggle(a.id, "preview")}
                            >
                              превью
                            </button>
                            <button
                              className={`alink${
                                openId === a.id && mode === "edit" ? " on" : ""
                              }`}
                              disabled={locked}
                              onClick={() => toggle(a.id, "edit")}
                            >
                              правка
                            </button>
                            <button
                              className="alink"
                              disabled={locked || published}
                              title={!hasPost ? "сначала создайте пост" : undefined}
                              onClick={async () => {
                                if (!a.post_text) {
                                  toast(
                                    "Сначала создайте пост — «сделать пост» или «правка».",
                                    "info",
                                  );
                                  return;
                                }
                                if (
                                  await confirmDialog(
                                    "Опубликовать пост в Telegram-канал?",
                                    "Опубликовать",
                                  )
                                ) {
                                  run(() => runAction(a.id, "publish"));
                                }
                              }}
                            >
                              опубликовать
                            </button>
                            <button
                              className={`alink${
                                openId === a.id && mode === "schedule" ? " on" : ""
                              }`}
                              disabled={locked || published}
                              onClick={() => toggle(a.id, "schedule")}
                            >
                              в очередь
                            </button>
                          </>
                        );
                      })()}
                    </div>
                  </td>
                </tr>
                {openId === a.id && (
                  <tr>
                    <td colSpan={7} className="panel-cell">
                      {mode === "preview" ? (
                        <PreviewPanel
                          text={a.post_text ?? ""}
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
            {text.trim() ? "Редактировать" : "Создать пост"}
          </button>
        </div>
        {text.trim() ? (
          <TelegramView text={text} image={image} />
        ) : (
          <div className="muted" style={{ fontSize: 13, padding: "8px 2px" }}>
            Поста ещё нет. «сделать пост» — сгенерирует ИИ, либо «Создать пост» —
            напишите вручную.
          </div>
        )}
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
  const [img, setImg] = useState<string | null>(article.image_url);
  const [imgBusy, setImgBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function onPickImage(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // чтобы можно было выбрать тот же файл повторно
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      setImgBusy(true);
      try {
        const url = await uploadImage(article.id, file.name, String(reader.result));
        setImg(url);
        await onChanged();
      } catch (err) {
        toast(`Ошибка: ${err instanceof Error ? err.message : String(err)}`, "error");
      } finally {
        setImgBusy(false);
      }
    };
    reader.readAsDataURL(file);
  }

  async function removeImage() {
    setImgBusy(true);
    try {
      await clearImage(article.id);
      setImg(null);
      await onChanged();
    } catch (err) {
      toast(`Ошибка: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setImgBusy(false);
    }
  }

  async function save() {
    setWorking(true);
    try {
      await savePost(article.id, text);
      await onChanged();
    } catch (e) {
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
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
    <div>
      <div className="toolbar">
        <button className="btn" onClick={onPreview}>
          Превью
        </button>
        <button className="btn btn-primary" disabled={working} onClick={save}>
          Сохранить
        </button>
      </div>
      <div className="panel">
        <div className="col">
          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              marginBottom: 10,
            }}
          >
            {img ? (
              <img
                src={img}
                alt=""
                style={{
                  width: 60,
                  height: 60,
                  objectFit: "cover",
                  borderRadius: 8,
                  border: "1px solid var(--line)",
                }}
              />
            ) : (
              <div
                style={{
                  width: 60,
                  height: 60,
                  borderRadius: 8,
                  border: "1px dashed var(--line-strong)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  color: "var(--muted)",
                }}
              >
                нет
              </div>
            )}
            <div
              style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}
            >
              <span className="muted" style={{ fontSize: 12 }}>
                Картинка поста
              </span>
              <button
                className="alink"
                disabled={imgBusy}
                onClick={() => fileRef.current?.click()}
              >
                {imgBusy ? "загрузка…" : "загрузить"}
              </button>
              {img && (
                <button className="alink" disabled={imgBusy} onClick={removeImage}>
                  убрать
                </button>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={onPickImage}
              />
            </div>
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
  const hasPost = !!article.post_text;

  async function wrap(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
      await onChanged();
    } catch (e) {
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
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
        {!hasPost && (
          <div style={{ fontSize: 13, marginBottom: 10, color: "#c02626" }}>
            Сначала создайте пост («сделать пост» или «правка») — иначе ставить в
            очередь нечего.
          </div>
        )}
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
            disabled={busy || !when || !hasPost}
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
            disabled={busy || !hasPost}
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
  const [query, setQuery] = useState(
    () => localStorage.getItem("search_query") ?? "",
  );
  const [busy, setBusy] = useState(false);
  const [webJob, setWebJob] = useState<CollectJob | null>(null);
  const [pending, setPending] = useState<Article[]>([]);
  const [actId, setActId] = useState<number | null>(null);
  const [sel, setSel] = useState<Set<number>>(new Set());

  const webActive =
    webJob?.status === "queued" || webJob?.status === "running";

  function setQueryPersist(v: string) {
    setQuery(v);
    localStorage.setItem("search_query", v);
  }

  async function loadPending() {
    try {
      setPending(await fetchPendingWeb(channel));
    } catch {
      /* при ошибке оставляем как есть */
    }
  }

  // подборка-черновики — при открытии и смене проекта
  useEffect(() => {
    loadPending();
    setSel(new Set());
  }, [channel]);

  // переподключаемся к уже идущему веб-поиску (после ухода со страницы/перезагрузки)
  useEffect(() => {
    collectActive()
      .then((jobs) => {
        const web = jobs.find((j) => j.query != null);
        if (web) setWebJob(web);
      })
      .catch(() => {});
  }, []);

  async function runWeb() {
    const q = query.trim();
    if (!q) return;
    setBusy(true);
    setWebJob(null);
    try {
      const r = await searchArticles(q, "web", channel);
      setWebJob(r.job ?? null);
    } catch (e) {
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
    } finally {
      setBusy(false);
    }
  }

  // веб-поиск исполняет воркер — опрашиваем задачу, по готовности грузим кандидатов
  useEffect(() => {
    if (!webJob || !webActive) return;
    const jobId = webJob.id;
    let stop = false;
    const id = setInterval(async () => {
      try {
        const j = await collectStatus(jobId);
        if (stop) return;
        setWebJob(j);
        if (j.status === "done") loadPending();
      } catch {
        /* разовые ошибки опроса игнорируем */
      }
    }, 2500);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, [webJob?.id, webActive]);

  async function decide(id: number, action: "approve" | "reject") {
    setActId(id);
    try {
      if (action === "approve") await approveArticle(id);
      else await runAction(id, "reject");
      setPending((p) => p.filter((a) => a.id !== id));
      setSel((prev) => {
        const n = new Set(prev);
        n.delete(id);
        return n;
      });
      onChanged(); // одобренная появится в общей таблице
    } catch (e) {
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
    } finally {
      setActId(null);
    }
  }

  function toggleSel(id: number) {
    setSel((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  async function bulk(action: "approve" | "reject") {
    const ids = [...sel];
    if (!ids.length) return;
    try {
      await bulkAction(ids, action);
      setSel(new Set());
      await loadPending();
      onChanged();
    } catch (e) {
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
    }
  }

  return (
    <div className="card" style={{ padding: "14px 16px", marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input
          value={query}
          onChange={(e) => setQueryPersist(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim() && !webActive) runWeb();
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
          className="btn btn-primary"
          disabled={busy || webActive || !query.trim()}
          onClick={runWeb}
        >
          {webActive ? "Ищу…" : "Найти в вебе"}
        </button>
      </div>

      {webJob && (
        <div
          style={{
            fontSize: 13,
            marginTop: 10,
            color: webJob.status === "error" ? "#c02626" : "var(--muted)",
          }}
        >
          {webActive
            ? "идёт веб-поиск… (LLM придумывает запросы, SearXNG тянет статьи — до минуты)"
            : webJob.status === "error"
              ? `веб-поиск упал: ${webJob.error ?? ""}`
              : `Найдено и предложено: ${webJob.result?.added ?? 0}. Запросы: ${(
                  (webJob.result?.queries as string[] | undefined) ?? []
                ).join(", ")}.`}
        </div>
      )}

      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        «Найти в вебе» — LLM придумает запросы, SearXNG принесёт новые статьи. Они
        сохраняются здесь как подборка-черновики (не пропадут при перезагрузке):
        «в Статьи» переносит в общую таблицу с оценкой LLM, «удалить» убирает из
        подборки. Можно отметить несколько и действовать пачкой.
      </div>

      {pending.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 8,
              flexWrap: "wrap",
            }}
          >
            <label
              style={{ display: "flex", alignItems: "center", gap: 6 }}
              title="выделить все"
            >
              <input
                type="checkbox"
                checked={pending.length > 0 && sel.size === pending.length}
                onChange={(e) =>
                  setSel(
                    e.target.checked
                      ? new Set(pending.map((a) => a.id))
                      : new Set(),
                  )
                }
              />
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                Подборка-черновики ({pending.length})
              </span>
            </label>
            {sel.size > 0 && (
              <>
                <button className="btn btn-primary" onClick={() => bulk("approve")}>
                  Перенести в Статьи ({sel.size})
                </button>
                <button className="btn" onClick={() => bulk("reject")}>
                  Удалить ({sel.size})
                </button>
              </>
            )}
          </div>
          {pending.map((a) => (
            <div
              key={a.id}
              style={{
                border: "1px solid var(--line)",
                borderRadius: 10,
                padding: "10px 12px",
                marginBottom: 8,
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "baseline",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                  <input
                    type="checkbox"
                    checked={sel.has(a.id)}
                    onChange={() => toggleSel(a.id)}
                  />
                  <a
                    className="title"
                    href={a.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontWeight: 600 }}
                  >
                    {a.title}
                  </a>
                </div>
                <div style={{ display: "flex", gap: 12, whiteSpace: "nowrap" }}>
                  <button
                    className="alink"
                    disabled={actId === a.id}
                    onClick={() => decide(a.id, "approve")}
                  >
                    в Статьи
                  </button>
                  <button
                    className="alink"
                    disabled={actId === a.id}
                    onClick={() => decide(a.id, "reject")}
                  >
                    удалить
                  </button>
                </div>
              </div>
              <div
                className="muted"
                style={{ fontSize: 12, marginTop: 2, marginLeft: 22 }}
              >
                {a.source}
                {a.relevance_score != null ? ` · оценка ${a.relevance_score}` : ""}
              </div>
              {a.post_text && (
                <div
                  style={{
                    fontSize: 13,
                    marginTop: 6,
                    marginLeft: 22,
                    whiteSpace: "pre-wrap",
                    maxHeight: 120,
                    overflow: "auto",
                  }}
                >
                  {a.post_text}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const CHANNEL_FIELDS: {
  key: keyof Channel;
  label: string;
  type: "text" | "int" | "bool" | "area";
}[] = [
  { key: "name", label: "Название проекта", type: "text" },
  { key: "bot_token", label: "Бот-токен", type: "text" },
  { key: "channel_id", label: "Telegram-канал (@name или -100…)", type: "text" },
  { key: "admin_user_id", label: "Admin user id", type: "text" },
  { key: "topic", label: "Тематика (для фильтра)", type: "area" },
  { key: "enabled", label: "Включён", type: "bool" },
  { key: "relevance_threshold", label: "Порог релевантности (0–10)", type: "int" },
  { key: "publish_interval_minutes", label: "Интервал публикации (мин)", type: "int" },
  { key: "collect_enabled", label: "Автосбор по расписанию", type: "bool" },
  { key: "collect_interval_minutes", label: "Интервал сбора (мин) ⟳", type: "int" },
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
  collect_enabled: true,
  collect_interval_minutes: 60,
  rss_feeds: "",
  habr_enabled: false,
  habr_hubs: "",
  arxiv_categories: "",
  reddit_subreddits: "",
  searxng_queries: "",
};

function nextCollectLabel(c: Channel | undefined): string {
  if (!c) return "";
  if (!c.collect_enabled) return "автосбор выключен";
  if (!c.next_collect_at) return "ожидает планировщик (бот запущен?)";
  const d = new Date(c.next_collect_at);
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const diffMin = Math.round((d.getTime() - Date.now()) / 60000);
  if (diffMin <= 0) return `сбор вот-вот (план. на ${time})`;
  if (diffMin < 60) return `через ${diffMin} мин (в ${time})`;
  const h = Math.floor(diffMin / 60);
  const m = diffMin % 60;
  return `через ${h} ч ${m} мин (в ${time})`;
}

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
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (editId === "new") return;
    if (!(await confirmDialog("Удалить проект? Его статьи отвяжутся.", "Удалить")))
      return;
    setBusy(true);
    try {
      await deleteChannel(editId);
      setEditId("new");
      setForm({ ...EMPTY_CHANNEL });
      await onChanged();
    } catch (e) {
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
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
            {c.name || `проект #${c.id}`}
          </button>
        ))}
        <button
          className={`chip${editId === "new" ? " active" : ""}`}
          onClick={() => pick("new")}
        >
          + новый проект
        </button>
      </div>
      {editId !== "new" && (
        <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
          Ближайший автосбор:{" "}
          {nextCollectLabel(channels.find((x) => x.id === editId))}
        </div>
      )}
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
            Удалить проект
          </button>
        )}
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Проект = свой Telegram-канал, бот-токен, тематика и источники. Автосбор и
        интервал сбора (⟳) подхватываются в течение минуты; остальное — со
        следующего прогона.
      </div>
    </div>
  );
}

const SETTING_LABELS: Record<string, string> = {
  llm_model: "Модель LLM",
  embed_model: "Модель эмбеддингов",
  max_articles_per_run: "Лимит статей за прогон (0 = без)",
  semantic_dedup_enabled: "Семантический дедуп",
  semantic_dedup_threshold: "Порог дедупа (0–1)",
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
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
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
      <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
        Здесь только общие для всего сервиса настройки. Тематика, порог
        релевантности, источники и интервалы сбора/публикации настраиваются в
        разделе «Проекты» отдельно для каждого проекта.
      </div>
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
      toast(`Ошибка: ${e instanceof Error ? e.message : String(e)}`, "error");
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
