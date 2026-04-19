"use client";

import { useCallback, useState, type ReactNode, type KeyboardEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/user-context";
import { getAdminQueue } from "@/lib/api";
import { ApiError } from "@/lib/api";

interface AdminGateProps {
  children: ReactNode;
}

export function AdminGate({ children }: AdminGateProps) {
  const { adminKey, setAdminKey } = useUser();
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authenticated, setAuthenticated] = useState(!!adminKey);

  const handleSubmit = useCallback(async () => {
    if (!input.trim()) return;

    setLoading(true);
    setError("");

    // Temporarily set the key so the api helper sends it
    setAdminKey(input.trim());

    try {
      await getAdminQueue();
      setAuthenticated(true);
    } catch (err) {
      // Clear key on failure
      setAdminKey("");
      if (err instanceof ApiError && err.status === 401) {
        setError("Wrong key \u2014 try again");
      } else {
        setError("Wrong key \u2014 try again");
      }
    } finally {
      setLoading(false);
    }
  }, [input, setAdminKey]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") handleSubmit();
    },
    [handleSubmit],
  );

  // Already authenticated via stored key
  if (authenticated && adminKey) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            <h2 className="text-lg font-semibold">Admin access</h2>
          </CardTitle>
          <CardDescription>
            Enter the ADMIN_KEY from your environment to continue.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Input
            type="password"
            placeholder="Admin key"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              setError("");
            }}
            onKeyDown={handleKeyDown}
          />
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <Button onClick={handleSubmit} disabled={loading || !input.trim()}>
            {loading ? "Verifying\u2026" : "Continue"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
