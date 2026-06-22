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

export type Stats = Record<string, number>;

export type ArticleAction = "draft" | "publish" | "reject";
