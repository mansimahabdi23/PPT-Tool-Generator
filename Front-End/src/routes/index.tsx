import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  FileCheck2,
  Palette,
  ShieldCheck,
  Sparkles,
  Upload,
  Wand2,
} from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "iMocha AI Presentation Studio" },
      {
        name: "description",
        content:
          "Upload any deck and get back a polished, on-brand, fully editable iMocha presentation in minutes.",
      },
      { property: "og:title", content: "iMocha AI Presentation Studio" },
      {
        property: "og:description",
        content:
          "Upload any deck and get back a polished, on-brand, fully editable iMocha presentation in minutes.",
      },
    ],
  }),
  component: Landing,
});

function Landing() {
  return (
    <div>
      {/* Hero */}
      <section className="relative pb-12 pt-16 md:pt-24">
        <div className="max-w-3xl">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-badge-fill px-3 py-1 text-xs font-medium text-badge-text">
            <Wand2 className="h-3.5 w-3.5" />
            Internal · Powered by iMocha brand intelligence
          </div>
          <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight text-ink md:text-6xl">
            Turn any deck into an{" "}
            <span className="text-gradient-hero">on-brand iMocha</span> presentation.
          </h1>
          <p className="mt-6 max-w-xl text-lg text-muted-foreground">
            Drop in a PowerPoint or start from a blank brief. We restyle layouts, apply
            approved visuals, and hand back a fully editable PPTX.
          </p>
        </div>
      </section>

      {/* Choice cards */}
      <section className="grid gap-4 pb-16 md:grid-cols-2">
        {/* Card A — Transform */}
        <div className="flex flex-col rounded-2xl border border-border bg-white p-7 shadow-sm">
          <div className="mb-5 inline-flex h-11 w-11 items-center justify-center rounded-lg bg-brand-orange/10 text-brand-orange">
            <Upload className="h-5 w-5" />
          </div>
          <h2 className="font-display text-2xl font-semibold text-ink">
            Transform an existing deck
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Upload a PowerPoint and we'll restyle it on-brand while keeping every fact,
            claim, and number intact.
          </p>
          <div className="mt-6 flex-1" />
          <Link
            to="/upload"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-orange px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-orange-deep"
          >
            <Upload className="h-4 w-4" />
            Upload a presentation
          </Link>
        </div>

        {/* Card B — Create */}
        <div className="flex flex-col rounded-2xl border border-border bg-white p-7 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-lg bg-brand-purple/10 text-brand-purple-base">
              <Sparkles className="h-5 w-5" />
            </div>
            <span className="inline-flex items-center rounded-full bg-badge-fill px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-badge-text">
              Coming soon
            </span>
          </div>
          <h2 className="font-display text-2xl font-semibold text-ink">
            Create a new presentation
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Start from a brief — topic, audience, key messages — and generate a brand-new
            on-brand iMocha deck from scratch.
          </p>
          <div className="mt-6 flex-1" />
          <Link
            to="/create"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-white px-5 py-3 text-sm font-semibold text-ink transition-colors hover:bg-surface"
          >
            <Sparkles className="h-4 w-4" />
            Create new
          </Link>
        </div>
      </section>

      <div className="pb-12">
        <Link
          to="/history"
          className="inline-flex items-center gap-2 text-sm font-medium text-ink hover:text-brand-orange-deep"
        >
          View recent transformations
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      {/* Value chips */}
      <section className="grid gap-4 pb-20 md:grid-cols-3">
        {[
          {
            icon: ShieldCheck,
            title: "On-brand, guaranteed",
            body: "Only approved templates, icons, and visuals from your asset library are used.",
          },
          {
            icon: FileCheck2,
            title: "Fully editable PPTX",
            body: "You get a real .pptx — edit every shape, swap content, present from PowerPoint.",
          },
          {
            icon: Palette,
            title: "Content never altered",
            body: "Facts, claims, and numbers are preserved. Only design and layout change.",
          },
        ].map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-2xl border border-border bg-white p-6">
            <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-brand-orange/10 text-brand-orange">
              <Icon className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-ink">{title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
