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
