"use client";

import { Toaster } from "sonner";

export function ToasterProvider() {
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        style: {
          background: "#111",
          border: "1px solid #1a1a1a",
          color: "#ededed",
        },
      }}
    />
  );
}
