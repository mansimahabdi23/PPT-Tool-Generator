import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  Check,
  FileSearch,
  Brain,
  Sparkles,
  Image as ImageIcon,
  Layout,
  ShieldCheck,
  Download,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { getJob } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import type { JobStatus } from "@/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/process/$jobId")({
  head: () => ({ meta: [{ title: "Processing · iMocha AI Studio" }] }),
  component: ProcessPage,
});

type StageKey =
  | "parsing"
  | "analyzing"
  | "retrieving"
  | "composing"
  | "validating"
  | "exporting";

const STAGES: { key: StageKey; label: string; sub: string; icon: typeof Check; pausesAt?: JobStatus }[] = [
  { key: "parsing", label: "Parse", sub: "Reading your slides", icon: FileSearch },
  { key: "analyzing", label: "Analyze & plan", sub: "Understanding content", icon: Brain, pausesAt: "plan_ready" },
  { key: "retrieving", label: "Retrieve assets", sub: "Finding approved visuals", icon: ImageIcon },
  { key: "composing", label: "Compose", sub: "Designing slides", icon: Layout },
  { key: "validating", label: "Validate", sub: "Checking brand & content", icon: ShieldCheck },
  { key: "exporting", label: "Export", sub: "Finalizing files", icon: Download },
];

const ORDER: JobStatus[] = [
  "parsing",
  "analyzing",
  "plan_ready",
  "retrieving",
  "composing",
  "validating",
  "exporting",
  "completed",
];

function stageState(stage: StageKey, status: JobStatus): "done" | "active" | "pending" {
  const stageIdx = ORDER.indexOf(stage);
  const statusIdx = ORDER.indexOf(status);
  // "analyzing" stage stays done once we're at plan_ready+
  if (stage === "analyzing" && status === "plan_ready") return "done";
  if (statusIdx > stageIdx) return "done";
  if (statusIdx === stageIdx) return "active";
  return "pending";
}

function ProcessPage() {
  const { jobId } = Route.useParams();
  const navigate = useNavigate();

  const { data: job, error } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (!s || s === "completed" || s === "failed" || s === "plan_ready") return false;
      return 700;
    },
  });

  useEffect(() => {
    if (job?.status === "plan_ready") {
      navigate({ to: "/plan/$jobId", params: { jobId } });
    } else if (job?.status === "completed") {
      navigate({ to: "/review/$jobId", params: { jobId } });
    }
  }, [job?.status, jobId, navigate]);

  if (error) {
    return (
      <div>
        <PageHeader title="Something went wrong" subtitle="We couldn't process this deck." />
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-5 w-5" /> Job not found or failed
          </div>
          <button
            onClick={() => navigate({ to: "/upload" })}
            className="mt-4 rounded-lg bg-brand-orange px-4 py-2 text-sm font-semibold text-white hover:bg-brand-orange-deep"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const status: JobStatus = job?.status ?? "parsing";

  return (
    <div>
      <PageHeader
        eyebrow={`Job · ${jobId}`}
        title="Transforming your deck"
        subtitle={
          job?.deckName ? (
            <>
              Working on <span className="font-medium text-ink">{job.deckName}</span> ·{" "}
              {job.slideCount} slides
            </>
          ) : (
            "Spinning up the pipeline…"
          )
        }
      />

      <div className="mx-auto max-w-2xl">
        <div className="rounded-2xl border border-border bg-white p-6 md:p-8">
          <ol className="relative space-y-1">
            {STAGES.map((stage, idx) => {
              const state = stageState(stage.key, status);
              const Icon = stage.icon;
              const isLast = idx === STAGES.length - 1;
              return (
                <li key={stage.key} className="relative flex gap-4 pb-6 last:pb-0">
                  {!isLast && (
                    <span
                      aria-hidden
                      className={cn(
                        "absolute left-[19px] top-10 h-full w-px",
                        state === "done" ? "bg-brand-orange" : "bg-border",
                      )}
                    />
                  )}
                  <div
                    className={cn(
                      "relative z-10 grid h-10 w-10 shrink-0 place-items-center rounded-full border-2 transition-colors",
                      state === "done" && "border-brand-orange bg-brand-orange text-white",
                      state === "active" && "border-brand-orange bg-white text-brand-orange",
                      state === "pending" && "border-border bg-white text-muted-foreground",
                    )}
                  >
                    {state === "done" ? (
                      <Check className="h-5 w-5" />
                    ) : state === "active" ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <Icon className="h-4 w-4" />
                    )}
                  </div>
                  <div className="min-w-0 pt-1.5">
                    <div
                      className={cn(
                        "text-sm font-semibold",
                        state === "pending" ? "text-muted-foreground" : "text-ink",
                      )}
                    >
                      {stage.label}
                    </div>
                    <div className="mt-0.5 text-sm text-muted-foreground">{stage.sub}</div>
                    {state === "active" && stage.key === "validating" && (
                      <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-brand-orange/10 px-2.5 py-0.5 text-xs font-medium text-brand-orange-deep">
                        <Sparkles className="h-3 w-3" /> Re-generating slide 7 — attempt 2 of 2
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Stay on this page — we'll move you forward automatically.
        </p>
      </div>
    </div>
  );
}
