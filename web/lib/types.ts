export interface App {
  id: number;
  slug: string;
  name: string;
  tagline?: string;
  description?: string;
  category?: string;
  tags?: string;
  icon?: string;
  status: string;
  version: number;
  delivery?: string;
  install_command?: string;
  source_url?: string;
  launch_url?: string;
  app_type?: string;
  author_name?: string;
  author_email?: string;
  install_count?: number;
  open_count?: number;
  avg_rating?: number;
  role_tags?: string | string[];
  created_at?: string;
  deployed_at?: string;
}

export interface Skill {
  id: number;
  title: string;
  description?: string;
  use_case?: string;
  category?: string;
  prompt_text?: string;
  author_name?: string;
  source_url?: string;
  upvotes: number;
  copy_count: number;
  created_at?: string;
}

export interface UserItem {
  id: number;
  tool_id: number;
  slug?: string;
  name?: string;
  tagline?: string;
  icon?: string;
  delivery?: string;
  source_url?: string;
  install_command?: string;
  open_count?: number;
  added_at?: string;
  last_opened_at?: string;
}

export interface Star {
  id: number;
  tool_id: number;
  slug?: string;
  name?: string;
  tagline?: string;
  icon?: string;
}

export interface Review {
  id: number;
  tool_id: number;
  rating: number;
  text?: string;
  user_name?: string;
  user_email?: string;
  created_at?: string;
}

export interface ClaudeRun {
  id: number;
  prompt: string;
  output?: string;
  status: "running" | "complete" | "error";
  exit_code?: number;
  started_at?: string;
  completed_at?: string;
}

export interface AdminStats {
  apps_live: number;
  apps_pending: number;
  skills_total: number;
}

export interface QueueItem extends App {
  html_length?: number;
}

export interface InspectionBadge {
  icon: string;
  label: string;
  detail?: string;
  tone?: "warn" | "info";
}
