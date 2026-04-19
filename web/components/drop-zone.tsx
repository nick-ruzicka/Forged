"use client";

import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

interface DropZoneProps {
  onFile: (file: File) => void;
  accept?: string;
}

export function DropZone({ onFile, accept }: DropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      setFileName(file.name);
      setFileSize(file.size);
      onFile(file);
    },
    [onFile],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors",
        dragOver
          ? "border-primary bg-primary/5"
          : "border-border hover:border-border-strong",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        className="hidden"
      />
      <Upload className="size-8 text-text-muted" />
      {fileName ? (
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-foreground">
            {fileName}
          </span>
          {fileSize != null && (
            <span className="text-xs text-text-muted">
              {formatSize(fileSize)}
            </span>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-0.5">
          <span className="text-sm text-text-secondary">
            Drag and drop a file here, or click to browse
          </span>
        </div>
      )}
    </div>
  );
}
