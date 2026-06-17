import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  CheckCircle2,
  Download,
  FileText,
  History as HistoryIcon,
  Loader2,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { getJob, getResult } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

export const Route = createFileRoute("/result/$jobId")({
  head: () => ({ meta: [{ title: "Download · iMocha AI Studio" }] }),
  component: ResultPage,
});

function ResultPage() {
  const { jobId } = Route.useParams();
  const navigate = useNavigate();
  const { data: job } = useQuery({ queryKey: ["job", jobId], queryFn: () => getJob(jobId) });
  const [downloading, setDownloading] = useState<"pptx" | "pdf" | null>(null);

  const handleDownload = async (kind: "pptx" | "pdf") => {
    setDownloading(kind);
    try {
      await getResult(jobId);
      // mock blob download
      const blob = new Blob([`iMocha mock ${kind.toUpperCase()} for job ${jobId}`], {
        type: kind === "pptx" ? "application/vnd.openxmlformats-officedocument.presentationml.presentation" : "application/pdf",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(job?.deckName ?? "presentation").replace(/\.[^.]+$/, "")}-imocha.${kind}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${kind.toUpperCase()} downloaded`);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Step 4 of 4"
        title="Your deck is ready"
        subtitle="Download the editable .pptx or share a PDF. We'll keep a copy in your history."
      />

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        {/* Summary */}
        <div className="rounded-2xl border border-border bg-white p-6 md:p-8">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-full bg-green-100 text-green-700">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <div>
              <div className="font-display text-xl font-semibold text-ink">Transformation complete</div>
              <div className="text-sm text-muted-foreground">{job?.deckName}</div>
            </div>
          </div>

          <dl className="mt-6 grid grid-cols-2 gap-y-4 text-sm md:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Slides</dt>
              <dd className="mt-1 font-display text-2xl font-semibold text-ink">
                {job?.slideCount ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Brand compliance</dt>
              <dd className="mt-1 inline-flex items-center gap-1.5 text-base font-semibold text-green-700">
                <ShieldCheck className="h-4 w-4" /> Passed
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Content fidelity</dt>
              <dd className="mt-1 text-base font-semibold text-ink">
                {job?.contentFidelity ?? "100% preserved"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Processing time</dt>
              <dd className="mt-1 text-base font-semibold text-ink">
                {job?.processingSeconds ? `${job.processingSeconds}s` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Restructuring</dt>
              <dd className="mt-1 text-base font-semibold text-ink">
                {job?.allowRestructure ? "Allowed" : "Preserved"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Job ID</dt>
              <dd className="mt-1 truncate text-xs font-mono text-ink">{jobId}</dd>
            </div>
          </dl>
        </div>

        {/* Download */}
        <div className="space-y-3">
          <button
            onClick={() => handleDownload("pptx")}
            disabled={downloading !== null}
            className="flex w-full items-center justify-between rounded-2xl bg-brand-orange p-6 text-left text-white shadow-sm transition-colors hover:bg-brand-orange-deep disabled:opacity-60"
          >
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider opacity-80">
                Editable
              </div>
              <div className="font-display text-2xl font-semibold">Download PPTX</div>
              <div className="mt-1 text-sm opacity-80">Open and edit in PowerPoint</div>
            </div>
            {downloading === "pptx" ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              <Download className="h-6 w-6" />
            )}
          </button>

          <button
            onClick={() => handleDownload("pdf")}
            disabled={downloading !== null}
            className="flex w-full items-center justify-between rounded-2xl border border-border bg-white p-6 text-left text-ink shadow-sm transition-colors hover:bg-surface disabled:opacity-60"
          >
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Share-ready
              </div>
              <div className="font-display text-2xl font-semibold">Download PDF</div>
              <div className="mt-1 text-sm text-muted-foreground">For email or quick preview</div>
            </div>
            {downloading === "pdf" ? (
              <Loader2 className="h-6 w-6 animate-spin text-brand-orange" />
            ) : (
              <FileText className="h-6 w-6 text-brand-orange" />
            )}
          </button>

          <div className="flex gap-2 pt-2">
            <button
              onClick={() => navigate({ to: "/upload" })}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-ink hover:bg-surface"
            >
              <RotateCcw className="h-4 w-4" /> Transform another
            </button>
            <Link
              to="/history"
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-ink hover:bg-surface"
            >
              <HistoryIcon className="h-4 w-4" /> View history
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
