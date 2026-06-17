import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { FileText, Info, Loader2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { uploadDeck } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/upload")({
  head: () => ({
    meta: [
      { title: "Upload a presentation · iMocha AI Studio" },
      { name: "description", content: "Upload a PowerPoint deck to transform into an on-brand iMocha presentation." },
    ],
  }),
  component: UploadPage,
});

const MAX_MB = 50;
const ACCEPTED = [".pptx", ".ppt"];

function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [allowRestructure, setAllowRestructure] = useState(false);
  const [dragging, setDragging] = useState(false);

  const mutation = useMutation({
    mutationFn: () => uploadDeck(file!, allowRestructure),
    onSuccess: ({ jobId }) => {
      toast.success("Upload received", { description: "Starting transformation…" });
      navigate({ to: "/process/$jobId", params: { jobId } });
    },
    onError: () => toast.error("Upload failed. Please try again."),
  });

  const validate = (f: File): string | null => {
    const name = f.name.toLowerCase();
    if (!ACCEPTED.some((ext) => name.endsWith(ext))) return "Only .pptx or .ppt files are supported.";
    if (f.size > MAX_MB * 1024 * 1024) return `File is larger than ${MAX_MB}MB.`;
    return null;
  };

  const handleFile = (f: File) => {
    const err = validate(f);
    setError(err);
    setFile(err ? null : f);
  };

  return (
    <div>
      <PageHeader
        eyebrow="Step 1 of 4"
        title="Upload a presentation"
        subtitle="Drop in a .pptx or .ppt file. We'll parse, restyle, and hand back a fully editable iMocha deck."
      />

      <div className="mx-auto max-w-3xl">
        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) handleFile(f);
          }}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed bg-white px-6 py-16 text-center transition-colors",
            dragging
              ? "border-brand-orange bg-brand-orange/5"
              : "border-border hover:border-brand-orange/60 hover:bg-surface/60",
          )}
        >
          <div className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-brand-orange/10 text-brand-orange">
            <Upload className="h-6 w-6" />
          </div>
          <div className="text-base font-semibold text-ink">
            Drop your deck here, or click to browse
          </div>
          <div className="mt-1 text-sm text-muted-foreground">
            .pptx or .ppt · up to {MAX_MB}MB
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pptx,.ppt,application/vnd.openxmlformats-officedocument.presentationml.presentation"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
        </div>

        {/* Selected file */}
        {file && (
          <div className="mt-4 flex items-center justify-between rounded-xl border border-border bg-white p-4">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-orange/10 text-brand-orange">
                <FileText className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-ink">{file.name}</div>
                <div className="text-xs text-muted-foreground">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB
                </div>
              </div>
            </div>
            <button
              onClick={() => setFile(null)}
              className="rounded-md p-2 text-muted-foreground hover:bg-surface hover:text-ink"
              aria-label="Remove file"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {error}
          </div>
        )}

        {/* Restructure toggle */}
        <div className="mt-6 flex items-start justify-between gap-4 rounded-xl border border-border bg-white p-5">
          <div>
            <Label htmlFor="restructure" className="flex items-center gap-2 text-sm font-semibold text-ink">
              Allow narrative restructuring
              <TooltipProvider delayDuration={150}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="inline-flex">
                      <Info className="h-3.5 w-3.5 text-muted-foreground" />
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    Lets the AI reorder, merge, or split slides for a cleaner flow. It still never
                    changes your facts or numbers.
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </Label>
            <p className="mt-1 text-sm text-muted-foreground">
              Off by default — slide order is preserved exactly.
            </p>
          </div>
          <Switch
            id="restructure"
            checked={allowRestructure}
            onCheckedChange={setAllowRestructure}
          />
        </div>

        {/* CTA */}
        <div className="mt-8 flex justify-end">
          <button
            disabled={!file || mutation.isPending}
            onClick={() => mutation.mutate()}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-orange px-6 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-orange-deep disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Uploading…
              </>
            ) : (
              <>Transform deck</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
