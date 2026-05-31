"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { useNiche, useUpdateNiche } from "@/lib/api/hooks";

export default function NicheDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);
  const niche = useNiche(id);
  const updateNiche = useUpdateNiche(id);

  const [draft, setDraft] = useState<Record<string, unknown>>({});

  // Populate draft once the data loads.
  useEffect(() => {
    if (niche.data) setDraft(niche.data as unknown as Record<string, unknown>);
  }, [niche.data]);

  if (niche.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (niche.isError) {
    return (
      <div>
        <p className="text-sm text-red-600">Failed to load niche.</p>
        <Button variant="outline" onClick={() => router.back()} className="mt-3">
          Back
        </Button>
      </div>
    );
  }

  function field<T>(key: string, fallback: T): T {
    const v = draft[key];
    return (v === undefined ? fallback : v) as T;
  }

  function setField(key: string, value: unknown) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function onSave() {
    // Build a minimal patch payload — only fields we expose for editing.
    const patch = {
      name: field("name", ""),
      description: field("description", ""),
      target_audience: field("target_audience", ""),
      tone: field("tone", ""),
      cta: field("cta", ""),
      content_pillars: field("content_pillars", [] as string[]),
      forbidden_topics: field("forbidden_topics", [] as string[]),
      hashtag_seeds: field("hashtag_seeds", [] as string[]),
      voice_id: field("voice_id", ""),
      voice_model: field("voice_model", null) as string | null,
      llm_provider: field("llm_provider", "openai"),
      llm_model: field("llm_model", "gpt-4o-mini"),
      image_provider: field("image_provider", "pexels"),
      voice_provider: field("voice_provider", "elevenlabs"),
      music_provider: field("music_provider", "elevenlabs"),
      music_enabled: field("music_enabled", true),
      video_length_default: field("video_length_default", "short"),
      image_aspect_default: field("image_aspect_default", "9:16"),
      topic_score_threshold: field("topic_score_threshold", 7.0),
    };
    updateNiche.mutate(patch, {
      onSuccess: () => toast.success("Niche saved"),
      onError: () => toast.error("Save failed"),
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{field<string>("name", "Niche")}</h1>
        <p className="mt-1 text-sm text-slate-500">Edit the personality + provider settings for this niche.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
          <CardDescription>What the niche is + who it&apos;s for.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Row label="Name">
            <Input value={field<string>("name", "")} onChange={(e) => setField("name", e.target.value)} />
          </Row>
          <Row label="Description">
            <Textarea
              rows={6}
              value={field<string>("description", "")}
              onChange={(e) => setField("description", e.target.value)}
            />
          </Row>
          <Row label="Target audience">
            <Input value={field<string>("target_audience", "")} onChange={(e) => setField("target_audience", e.target.value)} />
          </Row>
          <Row label="Tone">
            <Input value={field<string>("tone", "")} onChange={(e) => setField("tone", e.target.value)} />
          </Row>
          <Row label="Call-to-action">
            <Input value={field<string>("cta", "")} onChange={(e) => setField("cta", e.target.value)} />
          </Row>
          <Row label="Content pillars (one per line)">
            <Textarea
              rows={4}
              value={field<string[]>("content_pillars", []).join("\n")}
              onChange={(e) =>
                setField("content_pillars", e.target.value.split("\n").map((s) => s.trim()).filter(Boolean))
              }
            />
          </Row>
          <Row label="Forbidden topics (one per line)">
            <Textarea
              rows={3}
              value={field<string[]>("forbidden_topics", []).join("\n")}
              onChange={(e) =>
                setField("forbidden_topics", e.target.value.split("\n").map((s) => s.trim()).filter(Boolean))
              }
            />
          </Row>
          <Row label="Hashtag seeds (comma-separated)">
            <Input
              value={field<string[]>("hashtag_seeds", []).join(", ")}
              onChange={(e) =>
                setField("hashtag_seeds", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))
              }
            />
          </Row>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Providers</CardTitle>
          <CardDescription>Which AI services to use for this niche.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Row label="LLM provider">
              <Input value={field<string>("llm_provider", "openai")} onChange={(e) => setField("llm_provider", e.target.value)} />
            </Row>
            <Row label="LLM model">
              <Input value={field<string>("llm_model", "")} onChange={(e) => setField("llm_model", e.target.value)} />
            </Row>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Row label="Image provider">
              <Input value={field<string>("image_provider", "pexels")} onChange={(e) => setField("image_provider", e.target.value)} />
            </Row>
            <Row label="Image aspect default">
              <Input value={field<string>("image_aspect_default", "9:16")} onChange={(e) => setField("image_aspect_default", e.target.value)} />
            </Row>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Row label="Voice provider">
              <Input value={field<string>("voice_provider", "elevenlabs")} onChange={(e) => setField("voice_provider", e.target.value)} />
            </Row>
            <Row label="Voice ID">
              <Input value={field<string>("voice_id", "")} onChange={(e) => setField("voice_id", e.target.value)} />
            </Row>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Row label="Video length default">
              <select
                value={field<string>("video_length_default", "short")}
                onChange={(e) => setField("video_length_default", e.target.value)}
                className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
              >
                <option value="short">short (vertical 9:16 for Reels / Shorts / TikTok)</option>
                <option value="long">long (horizontal 16:9 for YouTube / LinkedIn / FB)</option>
              </select>
            </Row>
            <Row label="Topic score threshold">
              <Input
                type="number"
                step="0.1"
                value={field<number>("topic_score_threshold", 7.0)}
                onChange={(e) => setField("topic_score_threshold", Number(e.target.value))}
              />
            </Row>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="music-enabled"
              checked={field<boolean>("music_enabled", true)}
              onChange={(e) => setField("music_enabled", e.target.checked)}
            />
            <Label htmlFor="music-enabled">Music enabled</Label>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-3">
        <Button onClick={onSave} disabled={updateNiche.isPending}>
          {updateNiche.isPending ? "Saving…" : "Save changes"}
        </Button>
        <Button variant="outline" onClick={() => router.push("/niches")}>
          Back
        </Button>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
