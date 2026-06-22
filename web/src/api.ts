import type { Article, ArticleAction, Feed, LastRun, Stats } from "./types";

export async function fetchStats(): Promise<Stats> {
  const r = await fetch("/api/stats");
  return r.json();
}

export async function fetchLastRun(): Promise<LastRun> {
  const r = await fetch("/api/last-run");
  return r.json();
}

export async function fetchArticles(status?: string): Promise<Article[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(`/api/articles${q}`);
  return r.json();
}

export async function runAction(id: number, what: ArticleAction): Promise<void> {
  const r = await fetch(`/api/articles/${id}/${what}`, { method: "POST" });
  if (!r.ok) throw new Error(`${what}: HTTP ${r.status}`);
  const data = await r.json().catch(() => ({}));
  if (data && data.ok === false) {
    throw new Error(`${what}: сервер отклонил запрос (нет поста или ошибка модели)`);
  }
}

export async function scheduleArticle(
  id: number,
  when: string | null,
): Promise<void> {
  const r = await fetch(`/api/articles/${id}/schedule`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ when }),
  });
  if (!r.ok) throw new Error(`schedule: HTTP ${r.status}`);
  const data = await r.json().catch(() => ({}));
  if (data && data.ok === false) {
    throw new Error("не удалось запланировать (нет поста?)");
  }
}

export async function unscheduleArticle(id: number): Promise<void> {
  const r = await fetch(`/api/articles/${id}/unschedule`, { method: "POST" });
  if (!r.ok) throw new Error(`unschedule: HTTP ${r.status}`);
}

export async function setArticleStatus(id: number, status: string): Promise<void> {
  const r = await fetch(`/api/articles/${id}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`status: HTTP ${r.status}`);
  const data = await r.json().catch(() => ({}));
  if (data && data.ok === false) {
    throw new Error("статус изменить нельзя (опубликованная статья)");
  }
}

export async function collect(): Promise<void> {
  const r = await fetch("/api/collect", { method: "POST" });
  if (!r.ok) throw new Error(`collect: HTTP ${r.status}`);
}

export async function savePost(id: number, text: string): Promise<void> {
  const r = await fetch(`/api/articles/${id}/post`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(`save: HTTP ${r.status}`);
}

export async function revisePost(id: number, instruction: string): Promise<string> {
  const r = await fetch(`/api/articles/${id}/revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  });
  const data = await r.json();
  return (data.post as string) ?? "";
}

export async function fetchFeeds(): Promise<Feed[]> {
  const r = await fetch("/api/feeds");
  return r.json();
}

export async function addFeed(url: string): Promise<void> {
  const r = await fetch("/api/feeds", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!r.ok) throw new Error(`add feed: HTTP ${r.status}`);
}

export async function deleteFeed(id: number): Promise<void> {
  const r = await fetch(`/api/feeds/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete feed: HTTP ${r.status}`);
}

export interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

export async function chatArticle(id: number, messages: ChatMsg[]): Promise<string> {
  const r = await fetch(`/api/articles/${id}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
  const data = await r.json();
  return (data.reply as string) ?? "";
}
