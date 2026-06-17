import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ShieldCheck, Layers, X, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { approvePlan, getJob, getPlan } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import type { SlideType } from "@/types";

export const Route = createFileRoute("/plan/$jobId")({
  head: () => ({ meta: [{ title: "Review plan · iMocha AI Studio" }] }),
  component: PlanPage,
});

const typeLabels: Record<SlideType, string> = {
  title: "Title",
  agenda: "Agenda",
  content: "Content",
  data: "Data",
  divider: "Divider",
  closing: "Closing",
};

const typeColors: Record<SlideType, string> = {
  title: "bg-brand-orange/10 text-brand-orange-deep",
  agenda: "bg-badge-fill text-badge-text",
  content: "bg-surface text-ink",
  data: "bg-brand-purple/10 text-brand-purple",
  divider: "bg-zinc-200 text-zinc-700",
  closing: "bg-brand-orange/10 text-brand-orange-deep",
};

function PlanPage() {
  const { jobId } = Route.useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: job } = useQuery({ queryKey: ["job", jobId], queryFn: () => getJob(jobId) });
  const { data: plan, isLoading } = useQuery({
    queryKey: ["plan", jobId],
    queryFn: () => getPlan(jobId),
  });

  const approve = useMutation({
    mutationFn: () => approvePlan(jobId),
    onSuccess: () => {
      toast.success("Plan approved", { description: "Generating slides now…" });
      qc.invalidateQueries({ queryKey: ["job", jobId] });
      navigate({ to: "/process/$jobId", params: { jobId } });
    },
  });

  return (
    <div>
      <PageHeader
        eyebrow="Checkpoint"
        title="Review the plan"
        subtitle="Approve before we design your slides. No facts or numbers will be changed."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-3">
          {isLoading &&
            Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full rounded-xl" />
            ))}

          {plan?.map((p) => (
            <div
              key={p.id}
              className="flex flex-col gap-4 rounded-xl border border-border bg-white p-5 md:flex-row md:items-center"
            >
              <div className="flex shrink-0 items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-lg bg-surface font-display text-base font-semibold text-ink">
                  {p.index}
                </div>
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${typeColors[p.slideType]}`}
                >
                  {typeLabels[p.slideType]}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-ink">{p.plannedLayout}</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {p.assetTypes.map((t) => (
                    <span
                      key={t}
                      className="inline-flex items-center rounded-full border border-border bg-white px-2 py-0.5 text-[11px] font-medium text-ink/70"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
              {p.restructureNote && (
                <span className="inline-flex items-center gap-1 self-start rounded-full bg-badge-fill px-2.5 py-1 text-xs font-medium text-badge-text">
                  <Layers className="h-3 w-3" /> {p.restructureNote}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Side panel */}
        <aside className="space-y-4">
          <div className="rounded-2xl border border-border bg-white p-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
              <ShieldCheck className="h-4 w-4 text-brand-orange" />
              Content fidelity
            </div>
            <p className="text-sm text-muted-foreground">
              No facts, claims, or numbers will be changed. Only layouts, visuals, and styling.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-white p-5 text-sm">
            <div className="flex justify-between py-1">
              <span className="text-muted-foreground">Deck</span>
              <span className="font-medium text-ink">{job?.deckName ?? "—"}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-muted-foreground">Slides</span>
              <span className="font-medium text-ink">{plan?.length ?? "—"}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-muted-foreground">Restructuring</span>
              <span className="font-medium text-ink">
                {job?.allowRestructure ? "On" : "Off"}
              </span>
            </div>
          </div>
        </aside>
      </div>

      {/* Sticky actions */}
      <div className="sticky bottom-4 mt-10">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 rounded-2xl border border-border bg-white p-4 shadow-lg">
          <button
            onClick={() => navigate({ to: "/upload" })}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-ink hover:bg-surface"
          >
            <X className="h-4 w-4" /> Cancel
          </button>
          <button
            disabled={approve.isPending || !plan}
            onClick={() => approve.mutate()}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-orange px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-orange-deep disabled:opacity-50"
          >
            {approve.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowRight className="h-4 w-4" />
            )}
            Approve plan & generate
          </button>
        </div>
      </div>
    </div>
  );
}
