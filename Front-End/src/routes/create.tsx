import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useCallback } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  Plus,
  Sparkles,
  X,
} from "lucide-react";

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export const Route = createFileRoute("/create")({
  head: () => ({
    meta: [
      { title: "Create a new presentation — iMocha AI Presentation Studio" },
      {
        name: "description",
        content:
          "Start from a brief and generate a brand-new on-brand iMocha presentation from scratch.",
      },
      {
        property: "og:title",
        content: "Create a new presentation — iMocha AI Presentation Studio",
      },
      {
        property: "og:description",
        content:
          "Start from a brief and generate a brand-new on-brand iMocha presentation from scratch.",
      },
    ],
  }),
  component: CreatePage,
});

function CreatePage() {
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [objective, setObjective] = useState("");
  const [keyMessages, setKeyMessages] = useState<string[]>([]);
  const [newMessage, setNewMessage] = useState("");
  const [slideCount, setSlideCount] = useState<number[]>([10]);
  const [tone, setTone] = useState("");

  const showComingSoonToast = useCallback(() => {
    toast.info("Creating from scratch is coming soon. For now, upload an existing deck.");
  }, []);

  const addMessage = useCallback(() => {
    const trimmed = newMessage.trim();
    if (trimmed && !keyMessages.includes(trimmed)) {
      setKeyMessages((prev) => [...prev, trimmed]);
      setNewMessage("");
    }
  }, [newMessage, keyMessages]);

  const removeMessage = useCallback((msg: string) => {
    setKeyMessages((prev) => prev.filter((m) => m !== msg));
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        addMessage();
      }
    },
    [addMessage],
  );

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-4 pb-8 pt-10 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <div className="mb-2 inline-flex items-center gap-2">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-brand-orange">
              New presentation
            </div>
            <span className="inline-flex items-center rounded-full bg-badge-fill px-2.5 py-0.5 text-xs font-medium text-badge-text">
              Coming soon
            </span>
          </div>
          <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight text-ink md:text-5xl">
            Create a new presentation
          </h1>
          <p className="mt-3 max-w-2xl text-base text-muted-foreground md:text-lg">
            Describe what you need and we'll generate a fully branded iMocha deck — layouts,
            visuals, and content structure included.
          </p>
        </div>
      </div>

      {/* Form */}
      <div
        className="mx-auto max-w-2xl rounded-2xl border border-border bg-white p-6 shadow-sm md:p-8"
        onClick={showComingSoonToast}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") showComingSoonToast();
        }}
      >
        <div className="space-y-6">
          {/* Topic */}
          <div className="space-y-2">
            <Label htmlFor="topic">Topic</Label>
            <Input
              id="topic"
              placeholder="e.g. Q4 Sales Strategy, Product Roadmap 2026"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onClick={(e) => {
                e.stopPropagation();
                showComingSoonToast();
              }}
            />
          </div>

          {/* Audience */}
          <div className="space-y-2">
            <Label>Audience</Label>
            <Select
              value={audience}
              onValueChange={(v) => {
                setAudience(v);
                showComingSoonToast();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select audience type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sales">Sales</SelectItem>
                <SelectItem value="customer">Customer</SelectItem>
                <SelectItem value="executive">Executive</SelectItem>
                <SelectItem value="internal">Internal</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Objective */}
          <div className="space-y-2">
            <Label htmlFor="objective">Objective</Label>
            <Textarea
              id="objective"
              placeholder="What should this presentation achieve?"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              onClick={(e) => {
                e.stopPropagation();
                showComingSoonToast();
              }}
              rows={4}
            />
          </div>

          {/* Key messages */}
          <div className="space-y-2">
            <Label>Key messages</Label>
            <div className="flex gap-2">
              <Input
                placeholder="Add a key message and press Enter"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                onClick={(e) => {
                  e.stopPropagation();
                  showComingSoonToast();
                }}
              />
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  showComingSoonToast();
                  addMessage();
                }}
                className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border bg-surface px-3 text-sm font-medium text-ink transition-colors hover:bg-muted"
              >
                <Plus className="h-4 w-4" />
                Add
              </button>
            </div>
            {keyMessages.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {keyMessages.map((msg) => (
                  <span
                    key={msg}
                    className="inline-flex items-center gap-1 rounded-full bg-badge-fill px-3 py-1 text-xs font-medium text-badge-text"
                  >
                    {msg}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        showComingSoonToast();
                        removeMessage(msg);
                      }}
                      className="ml-0.5 inline-flex items-center justify-center rounded-full hover:text-ink"
                      aria-label={`Remove ${msg}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Slide count */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Approx. slide count</Label>
              <span className="text-sm font-semibold text-ink">{slideCount[0]} slides</span>
            </div>
            <Slider
              value={slideCount}
              onValueChange={(v) => {
                setSlideCount(v);
                showComingSoonToast();
              }}
              min={5}
              max={40}
              step={1}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>5</span>
              <span>40</span>
            </div>
          </div>

          {/* Tone */}
          <div className="space-y-2">
            <Label>Tone</Label>
            <Select
              value={tone}
              onValueChange={(v) => {
                setTone(v);
                showComingSoonToast();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select tone" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="professional">Professional</SelectItem>
                <SelectItem value="persuasive">Persuasive</SelectItem>
                <SelectItem value="data-driven">Data-driven</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Actions */}
        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex">
                  <button
                    type="button"
                    disabled
                    className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg bg-brand-orange/60 px-5 py-3 text-sm font-semibold text-white shadow-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      showComingSoonToast();
                    }}
                  >
                    <Sparkles className="h-4 w-4" />
                    Generate presentation
                  </button>
                </span>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p>Coming soon — for now, transform an existing deck.</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <Link
            to="/upload"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-white px-5 py-3 text-sm font-semibold text-ink transition-colors hover:bg-surface"
            onClick={(e) => e.stopPropagation()}
          >
            <ArrowLeft className="h-4 w-4" />
            Transform an existing deck instead
          </Link>
        </div>
      </div>
    </div>
  );
}
