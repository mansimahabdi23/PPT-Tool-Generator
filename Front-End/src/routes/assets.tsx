import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Plus, ShieldCheck, Search } from "lucide-react";
import { listAssets } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import type { AssetStatus, AssetType } from "@/types";

export const Route = createFileRoute("/assets")({
  head: () => ({
    meta: [
      { title: "Brand Assets · iMocha AI Studio" },
      { name: "description", content: "Manage approved brand assets for AI presentations." },
    ],
  }),
  component: AssetsPage,
});

function AssetsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["assets"], queryFn: listAssets });
  const [typeFilter, setTypeFilter] = useState<"all" | AssetType>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | AssetStatus>("all");
  const [q, setQ] = useState("");

  const filtered = data?.filter((a) => {
    if (typeFilter !== "all" && a.type !== typeFilter) return false;
    if (statusFilter !== "all" && a.status !== statusFilter) return false;
    if (q && !a.name.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });

  return (
    <div>
      <PageHeader
        eyebrow="Admin"
        title="Brand assets"
        subtitle="Approved templates, icons, infographics, and logos used to compose iMocha decks."
        actions={
          <Dialog>
            <DialogTrigger asChild>
              <button className="inline-flex items-center gap-2 rounded-lg bg-brand-orange px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-orange-deep">
                <Plus className="h-4 w-4" /> Add asset
              </button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add a brand asset</DialogTitle>
                <DialogDescription>
                  New assets go into review before being usable in transformations.
                </DialogDescription>
              </DialogHeader>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  toast.success("Asset submitted for review");
                }}
                className="space-y-4"
              >
                <div className="space-y-1.5">
                  <Label htmlFor="name">Name</Label>
                  <Input id="name" placeholder="e.g. Hero Cover — Q4 2026" required />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label>Type</Label>
                    <Select defaultValue="template">
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="template">Template</SelectItem>
                        <SelectItem value="icon">Icon</SelectItem>
                        <SelectItem value="infographic">Infographic</SelectItem>
                        <SelectItem value="logo">Logo</SelectItem>
                        <SelectItem value="chart">Chart</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Slot</Label>
                    <Select defaultValue="content">
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="cover">Cover</SelectItem>
                        <SelectItem value="content">Content</SelectItem>
                        <SelectItem value="divider">Divider</SelectItem>
                        <SelectItem value="closing">Closing</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="tags">Tags</Label>
                  <Input id="tags" placeholder="hero, q4, skill" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="file">File</Label>
                  <Input id="file" type="file" />
                </div>
                <DialogFooter>
                  <button
                    type="submit"
                    className="inline-flex items-center gap-2 rounded-lg bg-brand-orange px-4 py-2 text-sm font-semibold text-white hover:bg-brand-orange-deep"
                  >
                    Submit for review
                  </button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {/* Admin notice */}
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-border bg-badge-fill/50 p-4 text-sm text-badge-text">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          You're viewing this as a <strong>Brand Administrator</strong>. Only approved assets are
          eligible to be used in AI transformations.
        </div>
      </div>

      {/* Filters */}
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search assets…"
            className="pl-9"
          />
        </div>
        <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as typeof typeFilter)}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Type" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="template">Template</SelectItem>
            <SelectItem value="icon">Icon</SelectItem>
            <SelectItem value="infographic">Infographic</SelectItem>
            <SelectItem value="logo">Logo</SelectItem>
            <SelectItem value="chart">Chart</SelectItem>
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as typeof statusFilter)}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="deprecated">Deprecated</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading &&
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-full rounded-2xl" />
          ))}
        {filtered?.map((a) => (
          <div key={a.id} className="overflow-hidden rounded-2xl border border-border bg-white">
            <img src={a.thumbnailUrl} alt={a.name} className="block aspect-video w-full object-cover" />
            <div className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-ink">{a.name}</div>
                  <div className="text-xs capitalize text-muted-foreground">
                    {a.type} · {a.slot} · {a.version}
                  </div>
                </div>
                <StatusBadge status={a.status} />
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                <span>{a.owner}</span>
                {a.expiresAt && (
                  <span className="text-amber-700">
                    Expired {new Date(a.expiresAt).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        {filtered && filtered.length === 0 && !isLoading && (
          <div className="col-span-full rounded-2xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
            No assets match your filters.
          </div>
        )}
      </div>
    </div>
  );
}
