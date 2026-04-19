"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DropZone } from "@/components/drop-zone";
import { submitApp, submitFromGithub } from "@/lib/api";
import { useUser } from "@/lib/user-context";
import { trackMilestone } from "@/lib/milestones";
import type { App } from "@/lib/types";

const CATEGORIES = [
  "Development",
  "Testing",
  "Debugging",
  "Planning",
  "Code Review",
  "Documents",
  "Other",
];

type Mode = "paste" | "upload" | "github";

export default function PublishPage() {
  const { name: userName, email: userEmail, setIdentity } = useUser();

  // Mode
  const [mode, setMode] = useState<Mode>("paste");

  // Source content
  const [pasteContent, setPasteContent] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [githubUrl, setGithubUrl] = useState("");

  // Metadata
  const [appName, setAppName] = useState("");
  const [tagline, setTagline] = useState("");
  const [category, setCategory] = useState("Development");
  const [icon, setIcon] = useState("");
  const [description, setDescription] = useState("");
  const [authorName, setAuthorName] = useState("");
  const [authorEmail, setAuthorEmail] = useState("");

  // State
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [published, setPublished] = useState<App | null>(null);

  // Auto-fill from localStorage
  useEffect(() => {
    if (userName) setAuthorName(userName);
    if (userEmail) setAuthorEmail(userEmail);
  }, [userName, userEmail]);

  // Handle paste-mode drag-drop of .html files
  const handlePasteDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.name.endsWith(".html")) {
      file.text().then((text) => setPasteContent(text));
    }
  }, []);

  const handleSubmit = useCallback(async () => {
    setError("");

    if (!appName.trim()) {
      setError("Name is required");
      return;
    }
    if (!tagline.trim()) {
      setError("Tagline is required");
      return;
    }
    if (!authorEmail.trim()) {
      setError("Author email is required");
      return;
    }

    const metadata: Record<string, string> = {
      name: appName.trim(),
      tagline: tagline.trim(),
      category,
      icon: icon.trim() || "\u229E",
      description: description.trim() || "",
      author_name: authorName.trim() || "",
      author_email: authorEmail.trim(),
    };

    setSubmitting(true);
    try {
      let result: App;

      if (mode === "github") {
        if (!githubUrl.trim()) {
          setError("GitHub URL is required");
          setSubmitting(false);
          return;
        }
        result = await submitFromGithub(githubUrl.trim(), metadata);
      } else {
        let html = "";
        if (mode === "paste") {
          if (!pasteContent.trim()) {
            setError("Paste your HTML content");
            setSubmitting(false);
            return;
          }
          html = pasteContent;
        } else if (mode === "upload") {
          if (!uploadFile) {
            setError("Upload a file");
            setSubmitting(false);
            return;
          }
          html = await uploadFile.text();
        }
        result = await submitApp({ ...metadata, html });
      }

      // Persist identity
      if (authorName || authorEmail) {
        setIdentity(authorName, authorEmail);
      }

      const milestoneMsg = trackMilestone("first_submission");
      if (milestoneMsg) {
        toast(milestoneMsg);
      }

      setPublished(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }, [
    mode,
    appName,
    tagline,
    category,
    icon,
    description,
    authorName,
    authorEmail,
    pasteContent,
    uploadFile,
    githubUrl,
    setIdentity,
  ]);

  const handlePublishAnother = useCallback(() => {
    setPublished(null);
    setPasteContent("");
    setUploadFile(null);
    setGithubUrl("");
    setAppName("");
    setTagline("");
    setIcon("");
    setDescription("");
    setError("");
  }, []);

  // Success view
  if (published) {
    return (
      <div className="flex flex-col items-center gap-6 p-6 md:p-8">
        <div className="relative flex max-w-md flex-col items-center gap-5 rounded-2xl border border-border bg-card p-10 text-center">
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-primary/[0.03] to-transparent pointer-events-none" />
          <div className="relative flex size-16 items-center justify-center rounded-2xl bg-primary/10 text-4xl">
            🎉
          </div>
          <h2 className="relative text-2xl font-bold tracking-tight text-foreground">
            {published.name} published
          </h2>
          <p className="relative text-[15px] text-text-secondary leading-relaxed">
            Your app has been submitted and is pending review. You&apos;ll be
            notified once it&apos;s approved.
          </p>
          {published.slug && (
            <code className="rounded-md bg-muted px-3 py-1 font-mono text-xs text-text-secondary">
              /apps/{published.slug}
            </code>
          )}
          <div className="flex gap-2">
            {published.slug && (
              <Button
                variant="outline"
                nativeButton={false} render={<Link href={`/apps/${published.slug}`} />}
              >
                Open it
              </Button>
            )}
            <Button variant="outline" nativeButton={false} render={<Link href="/my-forge" />}>
              Go to My Forge
            </Button>
            <Button onClick={handlePublishAnother}>Publish another</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 p-6 md:p-8">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Publish</h1>
        <p className="text-[15px] text-text-secondary">
          Ship something your team will love. Paste HTML, upload, or pull from GitHub.
        </p>
      </div>

      {/* Mode selector */}
      <div className="inline-flex rounded-xl border border-border bg-surface-2 p-1">
        {(
          [
            { key: "paste", label: "Paste HTML" },
            { key: "upload", label: "Upload file" },
            { key: "github", label: "From GitHub" },
          ] as const
        ).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setMode(key)}
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition-all duration-150",
              mode === key
                ? "bg-white/[0.06] text-foreground shadow-sm"
                : "text-text-muted hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Source input */}
      {mode === "paste" && (
        <div className="flex flex-col gap-1">
          <Textarea
            className="min-h-[300px] font-mono text-xs"
            placeholder="Paste your HTML here..."
            value={pasteContent}
            onChange={(e) => setPasteContent(e.target.value)}
            onDrop={handlePasteDrop}
            onDragOver={(e) => e.preventDefault()}
          />
          <p className="text-xs text-text-muted">
            Tip: You can also drag-and-drop .html files into the textarea.
          </p>
        </div>
      )}

      {mode === "upload" && (
        <DropZone onFile={setUploadFile} accept=".html,.htm" />
      )}

      {mode === "github" && (
        <div className="flex flex-col gap-1">
          <Input
            placeholder="https://github.com/user/repo"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
          />
          <p className="text-xs text-text-muted">
            Tip: Private repos need a personal access token configured.
          </p>
        </div>
      )}

      {/* Metadata form */}
      <div className="flex flex-col gap-5 rounded-2xl border border-border bg-card p-6">
        <h3 className="text-[15px] font-semibold text-foreground">App details</h3>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-medium text-foreground/70">
              Name <span className="text-destructive">*</span>
            </label>
            <Input
              placeholder="My Cool App"
              maxLength={60}
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-medium text-foreground/70">
              Tagline <span className="text-destructive">*</span>
            </label>
            <Input
              placeholder="A short description"
              maxLength={100}
              value={tagline}
              onChange={(e) => setTagline(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-medium text-foreground/70">
              Category
            </label>
            <Select value={category} onValueChange={(v) => v && setCategory(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-medium text-foreground/70">
              Icon
            </label>
            <Input
              placeholder="⊞"
              maxLength={3}
              value={icon}
              onChange={(e) => setIcon(e.target.value)}
              className="w-20"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[13px] font-medium text-foreground/70">
            Description
          </label>
          <Textarea
            placeholder="A longer description of what your app does..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-medium text-foreground/70">
              Author name
            </label>
            <Input
              placeholder="Your name"
              value={authorName}
              onChange={(e) => setAuthorName(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-medium text-foreground/70">
              Author email <span className="text-destructive">*</span>
            </label>
            <Input
              placeholder="you@example.com"
              type="email"
              value={authorEmail}
              onChange={(e) => setAuthorEmail(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Submit */}
      <div className="flex items-center gap-4">
        <Button size="lg" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Publishing..." : "Publish App"}
        </Button>
        {error && (
          <span className="text-sm font-medium text-destructive">{error}</span>
        )}
      </div>
    </div>
  );
}
