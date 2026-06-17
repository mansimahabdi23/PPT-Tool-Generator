import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Check,
  RefreshCw,
  Flag,
  Edit3,
  Layers,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { getSlides, regenerateSlide, setSlideApproval } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type { TransformedSlide } from "@/types";

export const Route = createFileRoute("/review/$jobId")({
  head: () => ({ meta: [{ title: "Review transformations · iMocha AI Studio" }] }),
  component: ReviewPage,
});

function ReviewPage() {
  const { jobId } = Route.useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [editorOpen, setEditorOpen] = useState<number | null>(null);

  const { data: slides, isLoading } = useQuery({
    queryKey: ["slides", jobId],
    queryFn: () => getSlides(jobId),
  });

  const approveMut = useMutation({
    mutationFn: ({ slideId, approval }: { slideId: string; approval: TransformedSlide["approval"] }) =>
      setSlideApproval(jobId, slideId, approval),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["slides", jobId] }),
  });

  const regenMut = useMutation({
    mutationFn: (slideId: string) => regenerateSlide(jobId, slideId),
    onMutate: (slideId) => {
      qc.setQueryData<TransformedSlide[]>(["slides", jobId], (prev) =>
        prev?.map((s) => (s.id === slideId ? { ...s, approval: "regenerating" } : s)),
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["slides", jobId] });
      toast.success("Slide regenerated");
    },
  });

  const approvedCount = slides?.filter((s) => s.approval === "approved").length ?? 0;
  const total = slides?.length ?? 0;
  const allApproved = total > 0 && approvedCount === total;

  return (
    <div className="pb-24">
      <PageHeader
        eyebrow="Step 3 of 4"
        title="Review the transformation"
        subtitle="Side-by-side before/after for every slide. Content unchanged — only design has been updated."
      />

      <div className="space-y-5">
        {isLoading &&
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-72 w-full rounded-2xl" />
          ))}

        {slides?.map((slide) => (
          <SlideCard
            key={slide.id}
            slide={slide}
            onApprove={() => approveMut.mutate({ slideId: slide.id, approval: "approved" })}
            onFlag={() => approveMut.mutate({ slideId: slide.id, approval: "flagged" })}
            onRegen={() => regenMut.mutate(slide.id)}
            onEdit={() => setEditorOpen(slide.index)}
          />
        ))}
      </div>

      {/* Sticky bottom bar */}
      <div className="sticky bottom-4 mt-10">
        <div className="mx-auto flex max-w-3xl flex-col gap-3 rounded-2xl border border-border bg-white p-4 shadow-lg sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm font-medium text-ink">
            <span className="text-brand-orange">{approvedCount}</span> of {total} approved
          </div>
          <div className="flex gap-2">
            <button
              disabled={!slides || allApproved}
              onClick={() => {
                slides?.forEach((s) =>
                  approveMut.mutate({ slideId: s.id, approval: "approved" }),
                );
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-ink hover:bg-surface disabled:opacity-50"
            >
              <Check className="h-4 w-4" /> Approve all
            </button>
            <button
              disabled={!allApproved}
              onClick={() => navigate({ to: "/result/$jobId", params: { jobId } })}
              className="inline-flex items-center gap-2 rounded-lg bg-brand-orange px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-orange-deep disabled:cursor-not-allowed disabled:opacity-50"
            >
              Continue to download <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <Dialog open={editorOpen !== null} onOpenChange={(v) => !v && setEditorOpen(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit slide {editorOpen}</DialogTitle>
            <DialogDescription>
              The embedded editor (Office for the Web / OnlyOffice) will mount here. Edits will
              flow back to the deck.
            </DialogDescription>
          </DialogHeader>
          <div className="grid aspect-video place-items-center rounded-lg border border-dashed border-border bg-surface text-sm text-muted-foreground">
            Editor placeholder
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SlideCard({
  slide,
  onApprove,
  onFlag,
  onRegen,
  onEdit,
}: {
  slide: TransformedSlide;
  onApprove: () => void;
  onFlag: () => void;
  onRegen: () => void;
  onEdit: () => void;
}) {
  const isRegen = slide.approval === "regenerating";
  const isApproved = slide.approval === "approved";
  const isFlagged = slide.approval === "flagged";

  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border bg-white transition-colors",
        isApproved ? "border-green-300" : isFlagged ? "border-amber-300" : "border-border",
      )}
    >
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-8 w-8 place-items-center rounded-md bg-surface font-display text-sm font-semibold text-ink">
            {slide.index}
          </div>
          {slide.restructureNote ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-badge-fill px-2.5 py-0.5 text-xs font-medium text-badge-text">
              <Layers className="h-3 w-3" /> {slide.restructureNote}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
              <Check className="h-3 w-3" /> Content unchanged
            </span>
          )}
          {slide.changeChips.map((c) => (
            <span
              key={c}
              className="hidden rounded-full border border-border bg-white px-2 py-0.5 text-[11px] font-medium text-ink/70 md:inline-flex"
            >
              {c}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {isApproved && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
              <Check className="h-3 w-3" /> Approved
            </span>
          )}
          {isFlagged && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
              <Flag className="h-3 w-3" /> Flagged
            </span>
          )}
        </div>
      </div>

      {/* Desktop: side by side */}
      <div className="hidden md:grid md:grid-cols-2">
        <PreviewPanel label="Original" url={slide.originalPreviewUrl} muted />
        <PreviewPanel
          label="iMocha transformed"
          url={slide.transformedPreviewUrl}
          loading={isRegen}
        />
      </div>

      {/* Mobile: tabs */}
      <div className="md:hidden">
        <Tabs defaultValue="after" className="w-full">
          <TabsList className="mx-5 mt-3 grid w-[calc(100%-2.5rem)] grid-cols-2">
            <TabsTrigger value="before">Original</TabsTrigger>
            <TabsTrigger value="after">Transformed</TabsTrigger>
          </TabsList>
          <TabsContent value="before">
            <PreviewPanel label="Original" url={slide.originalPreviewUrl} muted />
          </TabsContent>
          <TabsContent value="after">
            <PreviewPanel label="Transformed" url={slide.transformedPreviewUrl} loading={isRegen} />
          </TabsContent>
        </Tabs>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={onApprove}
            disabled={isRegen || isApproved}
            className="inline-flex items-center gap-1.5 rounded-md bg-brand-orange px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-orange-deep disabled:opacity-50"
          >
            <Check className="h-3.5 w-3.5" /> Approve
          </button>
          <button
            onClick={onRegen}
            disabled={isRegen}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-xs font-semibold text-ink hover:bg-surface disabled:opacity-50"
          >
            {isRegen ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}{" "}
            Regenerate
          </button>
          <button
            onClick={onFlag}
            disabled={isRegen}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-xs font-semibold text-ink hover:bg-surface disabled:opacity-50"
          >
            <Flag className="h-3.5 w-3.5" /> Flag
          </button>
        </div>
        <button
          onClick={onEdit}
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-brand-purple hover:bg-badge-fill"
        >
          <Edit3 className="h-3.5 w-3.5" /> Edit in editor
        </button>
      </div>
    </div>
  );
}

function PreviewPanel({
  label,
  url,
  muted,
  loading,
}: {
  label: string;
  url: string;
  muted?: boolean;
  loading?: boolean;
}) {
  return (
    <div className={cn("relative", muted ? "bg-surface/60" : "bg-white")}>
      <div className="flex items-center justify-between px-5 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        <span>{label}</span>
      </div>
      <div className="relative px-5 pb-5">
        <div className="overflow-hidden rounded-lg border border-border">
          <img src={url} alt={label} className="block aspect-video w-full object-cover" />
          {loading && (
            <div className="absolute inset-0 mx-5 mb-5 grid place-items-center rounded-lg bg-white/80 backdrop-blur-sm">
              <div className="flex items-center gap-2 text-sm font-medium text-ink">
                <Loader2 className="h-4 w-4 animate-spin text-brand-orange" />
                Regenerating…
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
