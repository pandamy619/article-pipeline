export interface Article {
  id: number;
  status: string;
  relevance_score: number | null;
  relevance_reason: string | null;
  title: string;
  url: string;
  source: string;
  has_post: boolean;
}

export type Stats = Record<string, number>;

export type ArticleAction = "draft" | "publish" | "reject";
