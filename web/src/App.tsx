import { Fragment, useEffect, useState } from "react";
import {
  type ChatMsg,
  chatArticle,
  collect,
  fetchArticles,
  fetchStats,
  runAction,
  savePost,
  setArticleStatus,
} from "./api";
import type { Article, Stats } from "./types";

const STATUSES = ["new", "filtered", "drafted", "pending", "published", "rejected"];
const STATUS_RU: Record<string, string> = {
  new: "новая",
  filtered: "прошла фильтр",
  drafted: "черновик",
  pending: "на модерации",
  published: "опубликована",
  rejected: "отклонена",
};
type Mode = "preview" | "edit";

export default function App() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [filter, setFilter] = useState("");
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
    refresh(filter);
  }, [filter]);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
      await refresh(filter);
    } catch (e) {
      alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
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

  return (
    <div className="app">
      {busy && <div className="working-badge">работаю…</div>}

      <header className="topbar">
        <div>
          <h1>article-pipeline</h1>
          <p className="sub">панель модерации статей</p>
        </div>
        <button
          className="btn btn-primary"
          disabled={busy}
          onClick={() => run(() => collect())}
        >
          {busy ? "…" : "Собрать сейчас"}
        </button>
      </header>

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
                    <td colSpan={6} className="panel-cell">
                      {mode === "preview" ? (
                        <PreviewPanel
                          text={a.post_text}
                          image={a.image_url}
                          onEdit={() => setMode("edit")}
                        />
                      ) : (
                        <EditPanel
                          article={a}
                          onChanged={() => refresh(filter)}
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
                <td colSpan={6}>
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
