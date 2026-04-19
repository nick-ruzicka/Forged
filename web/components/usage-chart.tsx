"use client";

import type { UsageDay } from "@/lib/types";

interface UsageChartProps {
  sessions: UsageDay[];
}

export function UsageChart({ sessions }: UsageChartProps) {
  if (!sessions || sessions.length === 0) return null;

  const maxSec = Math.max(...sessions.map((d) => d.duration_sec), 1);
  const barW = 24;
  const gap = 4;
  const h = 48;
  const totalW = sessions.length * (barW + gap) - gap;

  return (
    <svg
      width={totalW}
      height={h + 18}
      viewBox={`0 0 ${totalW} ${h + 18}`}
      className="block"
    >
      {sessions.map((d, i) => {
        const barH = Math.max(
          (d.duration_sec / maxSec) * h,
          d.duration_sec > 0 ? 3 : 0,
        );
        const x = i * (barW + gap);
        const y = h - barH;
        const fill = d.duration_sec > 0 ? "#0066FF" : "#1a1a1a";
        const dayLabel = d.date.slice(5); // MM-DD

        return (
          <g key={d.date}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={barH}
              rx={3}
              fill={fill}
              opacity={0.8}
            />
            <text
              x={x + barW / 2}
              y={h + 14}
              textAnchor="middle"
              fill="#555"
              fontSize={9}
            >
              {dayLabel}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function formatDuration(sec: number): string {
  if (!sec || sec < 60) return "0m";
  if (sec < 3600) return Math.floor(sec / 60) + "m";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h + "h " + (m ? m + "m" : "");
}

export function timeAgo(isoStr: string | null): string {
  if (!isoStr) return "";
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

export function formatUptime(sec: number): string {
  if (!sec || sec < 60) return "just now";
  if (sec < 3600) return Math.floor(sec / 60) + "m";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h + "h " + m + "m";
}
