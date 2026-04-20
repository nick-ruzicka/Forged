"use client";

import { useMemo } from "react";
import Image from "next/image";

interface AppIconProps {
  name: string;
  slug: string;
  icon?: string | null;
  size?: number;
  className?: string;
}

/**
 * Deterministic monogram icon for apps.
 * If the app has a real icon (emoji or URL), it renders that.
 * Otherwise, generates a styled monogram from the app name with
 * colors derived deterministically from the slug.
 */
export function AppIcon({ name, slug, icon, size = 48, className = "" }: AppIconProps) {
  const monogram = useMemo(() => getMonogram(name), [name]);
  const colors = useMemo(() => getColors(slug), [slug]);

  // If the app has a real icon that isn't the default placeholder
  if (icon && icon !== "📦") {
    // Check if it's a URL (external brand icon)
    if (icon.startsWith("http") || icon.startsWith("/")) {
      return (
        <div
          className={`flex items-center justify-center overflow-hidden ${className}`}
          style={{
            width: size,
            height: size,
            borderRadius: size * 0.21,
          }}
        >
          <Image
            src={icon}
            alt={name}
            width={size}
            height={size}
            unoptimized
            className="object-cover"
          />
        </div>
      );
    }
    // Emoji icon — render in the monogram container for consistency
    return (
      <div
        className={`flex items-center justify-center ${className}`}
        style={{
          width: size,
          height: size,
          borderRadius: size * 0.21,
          background: `linear-gradient(135deg, ${colors.bg1}, ${colors.bg2})`,
          border: "1px solid rgba(255,255,255,0.04)",
        }}
      >
        <span style={{ fontSize: size * 0.5 }}>{icon}</span>
      </div>
    );
  }

  // Generated monogram
  const fontSize = monogram.length > 1 ? size * 0.35 : size * 0.4;

  return (
    <div
      className={`flex items-center justify-center select-none ${className}`}
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.21,
        background: `linear-gradient(135deg, ${colors.bg1}, ${colors.bg2})`,
        border: "1px solid rgba(255,255,255,0.04)",
      }}
    >
      <span
        style={{
          fontSize,
          fontWeight: 600,
          color: "rgba(255,255,255,0.92)",
          letterSpacing: "-0.02em",
          lineHeight: 1,
        }}
      >
        {monogram}
      </span>
    </div>
  );
}

function getMonogram(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function getColors(slug: string): { bg1: string; bg2: string } {
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = slug.charCodeAt(i) + ((hash << 5) - hash);
  }

  // HSL with low saturation (15-25%) and dark luminance (10-20%)
  const hue = ((hash & 0xff) * 360) / 255;
  const sat1 = 18 + ((hash >> 8) & 0x07); // 18-25%
  const lum1 = 12 + ((hash >> 11) & 0x07); // 12-19%
  const sat2 = 15 + ((hash >> 14) & 0x07); // 15-22%
  const lum2 = 10 + ((hash >> 17) & 0x07); // 10-17%

  return {
    bg1: `hsl(${hue.toFixed(0)}, ${sat1}%, ${lum1}%)`,
    bg2: `hsl(${((hue + 30) % 360).toFixed(0)}, ${sat2}%, ${lum2}%)`,
  };
}
