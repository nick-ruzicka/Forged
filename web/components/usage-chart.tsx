"use client";

import type { UsageDay } from "@/lib/types";

interface UsageChartProps {
  sessions: UsageDay[];
}

export function UsageChart({ sessions }: UsageChartProps) {
  if (!sessions || sessions.length === 0) return null;

  const maxSec = Math.max(...sessions.map((d) => d.duration_sec), 1);
  const barW = 28;
  const gap = 4;
  const h = 56;
  const totalW = sessions.length * (barW + gap) - gap;

  const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  return (
    <svg
      width={totalW}
      height={h + 20}
      viewBox={`0 0 ${totalW} ${h + 20}`}
      className="block"
    >
      {sessions.map((d, i) => {
        const barH = Math.max(
          (d.duration_sec / maxSec) * h,
          d.duration_sec > 0 ? 4 : 0,
        );
        const x = i * (barW + gap);
        const y = h - barH;
        const hasData = d.duration_sec > 0;

        // Get day name from date
        const dateObj = new Date(d.date + "T00:00:00");
        const dayLabel = dayNames[dateObj.getDay()];

        return (
          <g key={d.date}>
            {/* Background bar slot */}
            <rect
              x={x}
              y={0}
              width={barW}
              height={h}
              rx={6}
              fill="currentColor"
              className="text-surface-2"
              opacity={0.5}
            />
            {/* Active bar */}
            {hasData && (
              <rect
                x={x}
                y={y}
                width={barW}
                height={barH}
                rx={6}
                fill="url(#barGradient)"
                opacity={0.9}
              />
            )}
            {/* Day label */}
            <text
              x={x + barW / 2}
              y={h + 15}
              textAnchor="middle"
              fill="currentColor"
              className="text-text-muted"
              fontSize={10}
              fontWeight={500}
            >
              {dayLabel}
            </text>
          </g>
        );
      })}
      {/* Gradient definition */}
      <defs>
        <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="hsl(217, 92%, 60%)" />
          <stop offset="100%" stopColor="hsl(217, 92%, 45%)" />
        </linearGradient>
      </defs>
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
