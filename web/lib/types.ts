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
  install_meta?: string;
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
  // Subscription metadata (present when fetched via /me/skills)
  subscribed_at?: string;
  last_synced_at?: string;
  installed_version?: string;
  // Governance
  review_status?: string;
  review_id?: number;
  version?: number;
  blocked_reason?: string;
  approved_at?: string;
  blocked_at?: string;
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
  note?: string;
  user_name?: string;
  author_name?: string;
  user_email?: string;
  author_email?: string;
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

export interface CoInstall {
  id: number;
  slug: string;
  name: string;
  icon?: string;
  overlap: number;
}

export interface TrendingItem {
  id: number;
  slug: string;
  name: string;
  icon?: string;
  reason: string;
  installs_this_week?: number;
  team_installs?: number;
}

export interface TrendingData {
  role_trending: TrendingItem[];
  team_popular: TrendingItem[];
  role: string | null;
  team: string | null;
}

export interface UsageDay {
  date: string;
  duration_sec: number;
  count: number;
}

export interface UsageData {
  slug: string;
  sessions_7d: UsageDay[];
  total_sec_7d: number;
  session_count_7d: number;
  last_opened: string | null;
}

export interface SocialData {
  tool_id: number;
  install_count: number;
  team_install_count: number;
  team: string | null;
  avg_rating: number | null;
  review_count: number;
  role_concentration: {
    role: string;
    count: number;
    total: number;
  } | null;
  installs_this_week: number;
}

export interface RunningApp {
  slug: string;
  name: string;
  running: boolean;
  pid: number | null;
  uptime_sec?: number;
}

export interface RunningData {
  apps: RunningApp[];
}

export interface PrivacyData {
  scope: string;
  method: string;
  data_collected: string[];
  data_not_collected: string[];
  storage: string;
  currently_monitoring: { slug: string; process_name: string }[];
  monitor_interval_sec: number;
}
