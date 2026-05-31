"use client";

import { ArrowLeft, RefreshCw, Send, Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { useDeletePost, usePost, usePostNow, useRegeneratePost } from "@/lib/api/hooks";
import { formatCurrency } from "@/lib/utils";

const ALL_PLATFORMS_SHORT = ["instagram", "facebook", "tiktok", "youtube"];
const ALL_PLATFORMS_LONG = ["youtube", "facebook", "linkedin"];

export default function PostDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);
  const post = usePost(id);
  const regen = useRegeneratePost();
  const del = useDeletePost();
  const postNow = usePostNow(id);
  const [selected, setSelected] = useState<string[]>([]);

  if (post.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (post.isError || !post.data) {
    return (
      <div>
        <p className="text-sm text-red-600">Post not found.</p>
        <Button variant="outline" onClick={() => router.push("/posts")} className="mt-3">
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
      </div>
    );
  }

  const p = post.data;
  const platforms = p.video_length === "long" ? ALL_PLATFORMS_LONG : ALL_PLATFORMS_SHORT;

  function togglePlatform(platform: string) {
    setSelected((arr) => (arr.includes(platform) ? arr.filter((x) => x !== platform) : [...arr, platform]));
  }

  function onPostNow() {
    if (selected.length === 0) {
      toast.error("Pick at least one platform");
      return;
    }
    postNow.mutate(
      { platforms: selected },
      {
        onSuccess: (data) => {
          const successes = data.attempts.filter((a) => a.success);
          const failures = data.attempts.filter((a) => !a.success);
          if (successes.length > 0) {
            toast.success(
              `Posted to ${successes.map((s) => s.platform).join(", ")}`,
            );
          }
          if (failures.length > 0) {
            toast.error(`Failed on ${failures.map((f) => `${f.platform} (${f.error})`).join(", ")}`);
          }
        },
        onError: (err) =>
          toast.error(err instanceof ApiError ? err.message : "Post-now failed"),
      },
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => router.push("/posts")}>
          <ArrowLeft className="h-4 w-4" /> Back to posts
        </Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() =>
              regen.mutate(id, {
                onSuccess: () => toast.success("Pipeline started (sync)…"),
                onError: () => toast.error("Regenerate failed"),
              })
            }
            disabled={regen.isPending}
          >
            <RefreshCw className="h-4 w-4" /> {regen.isPending ? "Regenerating…" : "Regenerate"}
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              if (confirm("Delete this post + all its media?")) {
                del.mutate(id, {
                  onSuccess: () => {
                    toast.success("Deleted");
                    router.push("/posts");
                  },
                });
              }
            }}
          >
            <Trash2 className="h-4 w-4" /> Delete
          </Button>
        </div>
      </div>

      <div>
        <h1 className="text-2xl font-bold">Post #{p.id}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {p.status} · {p.video_length} · {p.image_count} images · ${(p.media_cost_usd ?? 0).toFixed(4)}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Video</CardTitle>
          <CardDescription>
            Files live on the backend filesystem ({p.video_format}, {Math.round(p.duration_sec)}s).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-slate-500">
            Video preview from the API isn&apos;t wired yet — Phase 4 adds an authenticated file-serving endpoint.
            For now the file is on the backend at the path stored in MediaAsset.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Caption</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">{p.caption}</pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hashtags</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {(p.hashtags || []).map((h) => (
              <span key={h} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                #{h}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Narrative script</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">{p.narrative_script}</pre>
        </CardContent>
      </Card>

      {p.status === "ready" && (
        <Card>
          <CardHeader>
            <CardTitle>Post now</CardTitle>
            <CardDescription>
              Bypass the schedule and post immediately to selected platforms.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {platforms.map((pl) => (
                <button
                  key={pl}
                  onClick={() => togglePlatform(pl)}
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    selected.includes(pl)
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  {pl}
                </button>
              ))}
            </div>
            <div className="flex gap-2 text-xs text-slate-500">
              <span>Selected: {selected.length > 0 ? selected.join(", ") : "(none)"}</span>
            </div>
            <Button onClick={onPostNow} disabled={postNow.isPending || selected.length === 0}>
              <Send className="h-4 w-4" /> {postNow.isPending ? "Posting…" : "Post now"}
            </Button>
            <p className="text-xs text-slate-500">
              You must have connected each selected platform via{" "}
              <a href="/socials" className="underline">
                Social Accounts
              </a>{" "}
              first.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
