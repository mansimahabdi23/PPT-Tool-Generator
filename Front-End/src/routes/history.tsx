import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { FileText, ArrowUpRight } from "lucide-react";
import { listHistory } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "History · iMocha AI Studio" },
      { name: "description", content: "Recent deck transformations." },
    ],
  }),
  component: HistoryPage,
});

function HistoryPage() {
  const { data, isLoading } = useQuery({ queryKey: ["history"], queryFn: listHistory });

  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title="History"
        subtitle="Your team's recent deck transformations."
      />

      <div className="overflow-hidden rounded-2xl border border-border bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-surface/60 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-5 py-3">Deck</th>
              <th className="px-5 py-3">Date</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Slides</th>
              <th className="px-5 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading &&
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i}>
                  <td colSpan={5} className="px-5 py-4">
                    <Skeleton className="h-6 w-full" />
                  </td>
                </tr>
              ))}
            {data?.map((j) => (
              <tr key={j.id} className="transition-colors hover:bg-surface/50">
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-brand-orange/10 text-brand-orange">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="font-medium text-ink">{j.deckName}</div>
                      <div className="text-xs text-muted-foreground">{j.id}</div>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4 text-muted-foreground">
                  {new Date(j.createdAt).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </td>
                <td className="px-5 py-4">
                  <StatusBadge status={j.status} />
                </td>
                <td className="px-5 py-4 text-ink">{j.slideCount || "—"}</td>
                <td className="px-5 py-4 text-right">
                  {j.status === "completed" ? (
                    <Link
                      to="/result/$jobId"
                      params={{ jobId: j.id }}
                      className="inline-flex items-center gap-1 text-sm font-medium text-brand-orange hover:text-brand-orange-deep"
                    >
                      Open <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
