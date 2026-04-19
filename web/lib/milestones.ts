const STORAGE_KEY = "forge_milestones";

const MESSAGES: Record<string, string> = {
  first_install: "You installed your first tool! Check it out in My Forge.",
  first_star: "You starred your first tool! Find your stars in My Forge.",
  first_submission: "Your app has been submitted for review!",
  first_approval: "Your app has been approved and is now live!",
};

export function trackMilestone(name: string): string | null {
  if (typeof window === "undefined") return null;

  let milestones: string[] = [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) milestones = JSON.parse(raw) as string[];
  } catch {
    // ignore
  }

  if (milestones.includes(name)) return null;

  milestones.push(name);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(milestones));

  return MESSAGES[name] ?? `Milestone unlocked: ${name}`;
}
