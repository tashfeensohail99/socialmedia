"use client";

import { ArrowUp, Plus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import {
  useCreateTopic,
  usePromoteTopic,
  useRejectTopic,
  useTopics,
} from "@/lib/api/hooks";
import { formatRelativeDate } from "@/lib/utils";

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "discovered", label: "Discovered" },
  { value: "scored", label: "Scored" },
  { value: "rejected", label: "Rejected" },
  { value: "used", label: "Used" },
];

export default function TopicsPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const topics = useTopics(statusFilter ? { status: statusFilter } : undefined);
  const create = useCreateTopic();
  const promote = usePromoteTopic();
  const reject = useRejectTopic();
  const [showAdd, setShowAdd] = useState(false);
  const [draft, setDraft] = useState({ title: "", content: "" });

  function onAdd(e: React.FormEvent) {
    e.preventDefault();
    create.mutate(draft, {
      onSuccess: () => {
        toast.success("Topic added");
        setShowAdd(false);
        setDraft({ title: "", content: "" });
      },
      onError: () => toast.error("Failed to add"),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Topics</h1>
          <p className="mt-1 text-sm text-slate-500">
            Candidate topics discovered by your sources. Promote to push to the front of the queue.
          </p>
        </div>
        <Button onClick={() => setShowAdd((v) => !v)}>
          <Plus className="h-4 w-4" />
          {showAdd ? "Cancel" : "Add manually"}
        </Button>
      </div>

      {showAdd && (
        <Card>
          <CardHeader>
            <CardTitle>Add a manual topic</CardTitle>
            <CardDescription>Bypasses discovery — goes straight into the queue as DISCOVERED status.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onAdd} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="t-title">Title</Label>
                <Input
                  id="t-title"
                  value={draft.title}
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="t-content">Context (optional)</Label>
                <Textarea
                  id="t-content"
                  rows={4}
                  value={draft.content}
                  onChange={(e) => setDraft({ ...draft, content: e.target.value })}
                />
              </div>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Adding…" : "Add topic"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0">
          <CardTitle>Topic queue</CardTitle>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </CardHeader>
        <CardContent>
          {topics.isLoading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : topics.data && topics.data.items.length > 0 ? (
            <ul className="divide-y divide-slate-100">
              {topics.data.items.map((t) => (
                <li key={t.id} className="flex items-start justify-between gap-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-slate-900">{t.title}</p>
                      {t.score !== null && t.score !== undefined && (
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                          {t.score}/10
                        </span>
                      )}
                      <StatusPill status={t.status} />
                    </div>
                    {t.suggested_angle && (
                      <p className="mt-1 text-xs text-slate-500 italic">
                        Angle: {t.suggested_angle}
                      </p>
                    )}
                    <p className="mt-0.5 text-xs text-slate-400">
                      {t.source_id ? `source #${t.source_id}` : "manual"} · {formatRelativeDate(t.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => promote.mutate(t.id, { onSuccess: () => toast.success("Promoted") })}
                      disabled={promote.isPending || t.status === "used"}
                    >
                      <ArrowUp className="h-4 w-4" /> Promote
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => reject.mutate(t.id, { onSuccess: () => toast.success("Rejected") })}
                      disabled={reject.isPending || t.status === "rejected" || t.status === "used"}
                    >
                      <X className="h-4 w-4" /> Reject
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">
              No topics yet. Set up a Topic Source or add one manually above.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const colors: Record<string, string> = {
    discovered: "bg-blue-100 text-blue-700",
    scored: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
    used: "bg-slate-100 text-slate-700",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase font-medium ${colors[status] || "bg-slate-100"}`}>
      {status}
    </span>
  );
}
