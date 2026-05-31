"use client";

import { Plus, Sparkles, Trash2, Wand2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import {
  useCreateNiche,
  useDeleteNiche,
  useDraftNiche,
  useNiches,
  type NicheDraft,
} from "@/lib/api/hooks";

const MIN_WORDS = 250;

export default function NichesPage() {
  const router = useRouter();
  const niches = useNiches();
  const createNiche = useCreateNiche();
  const deleteNiche = useDeleteNiche();
  const draftNiche = useDraftNiche();

  const [showCreate, setShowCreate] = useState(false);

  // Step 1: the client's free-text business description
  const [businessDesc, setBusinessDesc] = useState("");
  // Step 2: the AI-generated, editable draft (null until generated)
  const [draft, setDraft] = useState<NicheDraft | null>(null);

  const wordCount = useMemo(
    () => businessDesc.trim().split(/\s+/).filter(Boolean).length,
    [businessDesc],
  );
  const enoughWords = wordCount >= MIN_WORDS;

  function resetFlow() {
    setBusinessDesc("");
    setDraft(null);
    setShowCreate(false);
  }

  function onGenerate() {
    draftNiche.mutate(businessDesc, {
      onSuccess: (d) => {
        setDraft(d);
        toast.success("Niche generated — review and edit below, then create it.");
      },
      onError: (err) =>
        toast.error(err instanceof ApiError ? err.message : "AI generation failed"),
    });
  }

  function onCreate() {
    if (!draft) return;
    createNiche.mutate(
      {
        name: draft.name,
        description: draft.description,
        target_audience: draft.target_audience,
        tone: draft.tone,
        language: "en",
        content_pillars: draft.content_pillars,
        forbidden_topics: draft.forbidden_topics,
        cta: draft.cta,
        hashtag_seeds: draft.hashtag_seeds,
        video_length_default: "short",
        image_aspect_default: "9:16",
        image_count_short: 10,
        image_count_long: 20,
        llm_provider: "openai",
        llm_model: "gpt-4o-mini",
        image_provider: "pexels",
        voice_provider: "elevenlabs",
        voice_id: "EXAVITQu4vr4xnSDxMaL",
        voice_model: null,
        music_provider: "elevenlabs",
        music_enabled: true,
        topic_score_threshold: 7.0,
      },
      {
        onSuccess: (data) => {
          toast.success("Niche created — a free news feed was auto-added for it.");
          resetFlow();
          const created = data as unknown as { id: number };
          router.push(`/niches/${created.id}`);
        },
        onError: (err) =>
          toast.error(err instanceof ApiError ? err.message : "Failed to create niche"),
      },
    );
  }

  async function onDelete(id: number) {
    if (!confirm("Delete this niche? Posts and topics will be cascaded.")) return;
    deleteNiche.mutate(id, {
      onSuccess: () => toast.success("Niche deleted"),
      onError: () => toast.error("Delete failed"),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Niche</h1>
          <p className="mt-1 text-sm text-slate-500">
            Tell us what your business does — AI builds your content niche and the news feed it watches.
          </p>
        </div>
        <Button onClick={() => (showCreate ? resetFlow() : setShowCreate(true))}>
          <Plus className="h-4 w-4" />
          {showCreate ? "Cancel" : "New niche"}
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-blue-600" />
              Describe your business
            </CardTitle>
            <CardDescription>
              Write at least {MIN_WORDS} words about what you do — your services, who your
              customers are, what kind of news matters to them, and the kind of posts you want.
              We&apos;ll use your OpenAI key to turn it into a full content niche.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="biz">What does your business do?</Label>
              <Textarea
                id="biz"
                rows={10}
                placeholder="Example: Falisha is an overseas recruitment agency in Pakistan. We connect Pakistani workers — electricians, AC technicians, drivers, welders, nurses, construction and restaurant staff — with verified employers in the Gulf (Saudi Arabia, UAE, Qatar). We handle CVs, documents, medicals, visas and work permits. Our audience is job seekers who want Gulf jobs, plus employers who need manpower. We want posts about Gulf hiring demand, new visa rules, profession-specific job demand, scam awareness, and document guidance — always tying back to how Falisha helps…"
                value={businessDesc}
                onChange={(e) => setBusinessDesc(e.target.value)}
              />
              <div className="flex items-center justify-between text-xs">
                <span className={enoughWords ? "text-green-600" : "text-slate-500"}>
                  {wordCount} / {MIN_WORDS} words {enoughWords ? "✓" : ""}
                </span>
                {!enoughWords && (
                  <span className="text-slate-400">
                    {MIN_WORDS - wordCount} more words needed
                  </span>
                )}
              </div>
            </div>
            <Button
              onClick={onGenerate}
              disabled={!enoughWords || draftNiche.isPending}
            >
              <Wand2 className="h-4 w-4" />
              {draftNiche.isPending ? "Generating with AI…" : "Generate my niche"}
            </Button>
          </CardContent>
        </Card>
      )}

      {showCreate && draft && (
        <Card className="border-blue-200">
          <CardHeader>
            <CardTitle>Review your niche</CardTitle>
            <CardDescription>
              AI generated this from your description. Edit anything, then create it. The bot will
              search news for your content pillars and post videos that tie back to your business.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Name">
              <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </Field>
            <Field label="Description">
              <Textarea
                rows={4}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </Field>
            <Field label="Target audience">
              <Input
                value={draft.target_audience}
                onChange={(e) => setDraft({ ...draft, target_audience: e.target.value })}
              />
            </Field>
            <Field label="Tone">
              <Input value={draft.tone} onChange={(e) => setDraft({ ...draft, tone: e.target.value })} />
            </Field>
            <Field label="News topics to watch (content pillars — one per line)">
              <Textarea
                rows={5}
                value={draft.content_pillars.join("\n")}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    content_pillars: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                  })
                }
              />
              <p className="mt-1 text-xs text-slate-500">
                These drive the free Google News feed. Keep them as concrete search terms.
              </p>
            </Field>
            <Field label="Forbidden topics (one per line)">
              <Textarea
                rows={3}
                value={draft.forbidden_topics.join("\n")}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    forbidden_topics: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                  })
                }
              />
            </Field>
            <Field label="Call-to-action">
              <Input value={draft.cta} onChange={(e) => setDraft({ ...draft, cta: e.target.value })} />
            </Field>
            <Field label="Hashtag seeds (comma-separated)">
              <Input
                value={draft.hashtag_seeds.join(", ")}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    hashtag_seeds: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                  })
                }
              />
            </Field>

            <div className="flex gap-3 pt-2">
              <Button onClick={onCreate} disabled={createNiche.isPending}>
                {createNiche.isPending ? "Creating…" : "Create this niche"}
              </Button>
              <Button variant="outline" onClick={onGenerate} disabled={draftNiche.isPending}>
                <Wand2 className="h-4 w-4" />
                Regenerate
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Your niches</CardTitle>
        </CardHeader>
        <CardContent>
          {niches.isLoading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : niches.data && niches.data.items.length > 0 ? (
            <ul className="divide-y divide-slate-100">
              {niches.data.items.map((n) => (
                <li key={n.id} className="flex items-center justify-between py-3">
                  <div>
                    <Link
                      href={`/niches/${n.id}`}
                      className="text-sm font-medium text-slate-900 hover:underline"
                    >
                      {n.name}
                    </Link>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {n.target_audience} · {n.llm_model} · {n.video_length_default}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(n.id)}
                    disabled={deleteNiche.isPending}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">
              No niches yet. Click &quot;New niche&quot; above and describe your business to get started.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
