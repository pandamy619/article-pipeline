export interface Article {
  id: number;
  status: string;
  relevance_score: number | null;
  relevance_reason: string | null;
  title: string;
  url: string;
  source: string;
  has_post: boolean;
  post_text: string | null;
  image_url: string | null;
}

export interface Feed {
  id: number | null;
  url: string;
  enabled: boolean;
  source: string;
}

export interface LastRun {
  exists: boolean;
  created_at?: string;
  ok?: boolean;
  error?: string | null;
  collected?: number;
  added?: number;
  duplicates?: number;
  semantic_duplicates?: number;
  filtered?: number;
  rejected?: number;
  drafted?: number;
}

export type Stats = Record<string, number>;

export type ArticleAction = "draft" | "publish" | "reject";
