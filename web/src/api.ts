import type {
  Article,
  ArticleAction,
  Channel,
  CollectJob,
  Feed,
  LastRun,
  Stats,
} from "./types";

const TOKEN_KEY = "admin_token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}
export function setToken(t: string): void {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class AuthError extends Error {}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const t = getToken();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

async function req(path: string, opts: RequestInit = {}): Promise<Response> {
  const r = await fetch(path, {
    ...opts,
    headers: authHeaders((opts.headers as Record<string, string>) ?? {}),
  });
  if (r.status === 401) {
    clearToken();
    throw new AuthError("unauthorized");
  }
  return r;
}

export async function checkAuth(token: string): Promise<boolean> {
  const r = await fetch("/api/auth/check", {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  return r.ok;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export async function fetchStats(channel?: number | null): Promise<Stats> {
  const q = channel != null ? `?channel=${channel}` : "";
  return (await req(`/api/stats${q}`)).json();
}

export async function fetchLastRun(): Promise<LastRun> {
  return (await req("/api/last-run")).json();
}

export async function fetchArticles(
  status?: string,
  channel?: number | null,
): Promise<Article[]> {
  const p = new URLSearchParams();
  if (status) p.set("status", status);
  if (channel != null) p.set("channel", String(channel));
  const q = p.toString() ? `?${p.toString()}` : "";
  return (await req(`/api/articles${q}`)).json();
}

export async function fetchChannels(): Promise<Channel[]> {
  return (await req("/api/channels")).json();
}

export async function createChannel(data: Partial<Channel>): Promise<Channel> {
  const r = await req("/api/channels", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error(`create channel: HTTP ${r.status}`);
  return r.json();
}

export async function updateChannel(
  id: number,
  data: Partial<Channel>,
): Promise<void> {
  const r = await req(`/api/channels/${id}`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error(`update channel: HTTP ${r.status}`);
}

export async function deleteChannel(id: number): Promise<void> {
  const r = await req(`/api/channels/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete channel: HTTP ${r.status}`);
}

export async function runAction(id: number, what: ArticleAction): Promise<void> {
  const r = await req(`/api/articles/${id}/${what}`, { method: "POST" });
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
  const r = await req(`/api/articles/${id}/schedule`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ when }),
  });
  if (!r.ok) throw new Error(`schedule: HTTP ${r.status}`);
  const data = await r.json().catch(() => ({}));
  if (data && data.ok === false) {
    throw new Error("не удалось запланировать (нет поста?)");
  }
}

export async function unscheduleArticle(id: number): Promise<void> {
  const r = await req(`/api/articles/${id}/unschedule`, { method: "POST" });
  if (!r.ok) throw new Error(`unschedule: HTTP ${r.status}`);
}

export async function setArticleStatus(id: number, status: string): Promise<void> {
  const r = await req(`/api/articles/${id}/status`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`status: HTTP ${r.status}`);
  const data = await r.json().catch(() => ({}));
  if (data && data.ok === false) {
    throw new Error("статус изменить нельзя (опубликованная статья)");
  }
}

export async function collect(channel?: number | null): Promise<CollectJob> {
  const q = channel != null ? `?channel=${channel}` : "";
  const r = await req(`/api/collect${q}`, { method: "POST" });
  if (!r.ok) throw new Error(`collect: HTTP ${r.status}`);
  return r.json();
}

export async function collectStatus(id: number): Promise<CollectJob> {
  const r = await req(`/api/collect/status/${id}`);
  if (!r.ok) throw new Error(`collect status: HTTP ${r.status}`);
  return r.json();
}

export async function collectActive(): Promise<CollectJob[]> {
  const r = await req("/api/collect/active");
  if (!r.ok) throw new Error(`collect active: HTTP ${r.status}`);
  return r.json();
}

export async function savePost(id: number, text: string): Promise<void> {
  const r = await req(`/api/articles/${id}/post`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(`save: HTTP ${r.status}`);
}

export async function revisePost(id: number, instruction: string): Promise<string> {
  const r = await req(`/api/articles/${id}/revise`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ instruction }),
  });
  const data = await r.json();
  return (data.post as string) ?? "";
}

export interface SettingsResponse {
  settings: Record<string, unknown>;
  types: Record<string, string>;
}

export async function fetchSettings(): Promise<SettingsResponse> {
  return (await req("/api/settings")).json();
}

export async function saveSetting(key: string, value: string): Promise<void> {
  const r = await req("/api/settings", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ key, value }),
  });
  if (!r.ok) throw new Error(`setting: HTTP ${r.status}`);
}

export async function bulkAction(ids: number[], action: string): Promise<number> {
  const r = await req("/api/articles/bulk", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ ids, action }),
  });
  if (!r.ok) throw new Error(`bulk: HTTP ${r.status}`);
  const data = await r.json().catch(() => ({}));
  return (data.done as number) ?? 0;
}

export async function fetchFeeds(): Promise<Feed[]> {
  return (await req("/api/feeds")).json();
}

export async function addFeed(url: string): Promise<void> {
  const r = await req("/api/feeds", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ url }),
  });
  if (!r.ok) throw new Error(`add feed: HTTP ${r.status}`);
}

export async function deleteFeed(id: number): Promise<void> {
  const r = await req(`/api/feeds/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete feed: HTTP ${r.status}`);
}

export interface SearchResult {
  id: number;
  title: string;
  url: string;
  status: string;
  channel_id: number | null;
  similarity: number;
}

export interface SearchResponse {
  mode: string;
  results?: SearchResult[];
  added?: number;
  queries?: string[];
}

export async function searchArticles(
  query: string,
  mode: "semantic" | "web",
  channel: number | null,
): Promise<SearchResponse> {
  const r = await req("/api/search", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ query, mode, channel_id: channel }),
  });
  if (!r.ok) throw new Error(`search: HTTP ${r.status}`);
  return r.json();
}

export interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

export async function chatArticle(id: number, messages: ChatMsg[]): Promise<string> {
  const r = await req(`/api/articles/${id}/chat`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ messages }),
  });
  const data = await r.json();
  return (data.reply as string) ?? "";
}
