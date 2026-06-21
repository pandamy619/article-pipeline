import type { Article, ArticleAction, Stats } from "./types";

export async function fetchStats(): Promise<Stats> {
  const r = await fetch("/api/stats");
  return r.json();
}

export async function fetchArticles(status?: string): Promise<Article[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(`/api/articles${q}`);
  return r.json();
}

export async function runAction(id: number, what: ArticleAction): Promise<void> {
  await fetch(`/api/articles/${id}/${what}`, { method: "POST" });
}

export async function collect(): Promise<void> {
  await fetch("/api/collect", { method: "POST" });
}

export async function savePost(id: number, text: string): Promise<void> {
  await fetch(`/api/articles/${id}/post`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
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
