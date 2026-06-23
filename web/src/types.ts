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
  scheduled_at: string | null;
  channel_id: number | null;
}

export interface Channel {
  id: number;
  name: string;
  bot_token: string;
  channel_id: string;
  admin_user_id: string;
  topic: string;
  enabled: boolean;
  relevance_threshold: number;
  publish_interval_minutes: number;
  collect_enabled: boolean;
  collect_interval_minutes: number;
  next_collect_at: string | null;
  rss_feeds: string;
  habr_enabled: boolean;
  habr_hubs: string;
  arxiv_categories: string;
  reddit_subreddits: string;
  searxng_queries: string;
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
