"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import {
  useCreatePostingRule,
  useDeletePostingRule,
  usePostingRules,
} from "@/lib/api/hooks";

const RULE_TYPES = [
  { value: "peak_hours", label: "Peak hours", help: 'Limit scheduling to specific hours. Example: {"hours": [18, 20, 21], "tz": "UTC"}' },
  { value: "quiet_hours", label: "Quiet hours", help: 'Avoid scheduling during these hours. Example: {"start": 1, "end": 7}' },
  { value: "spacing", label: "Spacing", help: 'Minimum gap between posts. Example: {"min_gap_minutes": 90}' },
  { value: "platform_priority", label: "Platform priority", help: 'Pick a primary platform when conflicts arise. Example: {"primary": "youtube"}' },
];

export default function RulesPage() {
  const rules = usePostingRules();
  const create = useCreatePostingRule();
  const del = useDeletePostingRule();
  const [showAdd, setShowAdd] = useState(false);
  const [draft, setDraft] = useState({
    name: "",
    type: "peak_hours",
    params_raw: '{"hours": [18, 20, 21], "tz": "UTC"}',
    enabled: true,
  });

  function onAdd(e: React.FormEvent) {
    e.preventDefault();
    let params_json: Record<string, unknown>;
    try {
      params_json = JSON.parse(draft.params_raw);
    } catch {
      toast.error("params_json must be valid JSON");
      return;
    }
    create.mutate(
      { name: draft.name, type: draft.type, params_json, enabled: draft.enabled },
      {
        onSuccess: () => {
          toast.success("Rule added");
          setShowAdd(false);
        },
        onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed"),
      },
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Posting Rules</h1>
          <p className="mt-1 text-sm text-slate-500">
            Constraints applied when the scheduler picks a posting time for ready posts.
          </p>
        </div>
        <Button onClick={() => setShowAdd((v) => !v)}>
          <Plus className="h-4 w-4" />
          {showAdd ? "Cancel" : "New rule"}
        </Button>
      </div>

      {showAdd && (
        <Card>
          <CardHeader>
            <CardTitle>Add rule</CardTitle>
            <CardDescription>Rules are evaluated when a Post becomes READY.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onAdd} className="space-y-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} required />
              </div>
              <div className="space-y-2">
                <Label>Type</Label>
                <select
                  value={draft.type}
                  onChange={(e) => {
                    const defaults: Record<string, string> = {
                      peak_hours: '{"hours": [18, 20, 21], "tz": "UTC"}',
                      quiet_hours: '{"start": 1, "end": 7}',
                      spacing: '{"min_gap_minutes": 90}',
                      platform_priority: '{"primary": "youtube"}',
                    };
                    setDraft({ ...draft, type: e.target.value, params_raw: defaults[e.target.value] || "{}" });
                  }}
                  className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                >
                  {RULE_TYPES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-500">{RULE_TYPES.find((r) => r.value === draft.type)?.help}</p>
              </div>
              <div className="space-y-2">
                <Label>Params (JSON)</Label>
                <Textarea
                  rows={4}
                  value={draft.params_raw}
                  onChange={(e) => setDraft({ ...draft, params_raw: e.target.value })}
                  className="font-mono text-xs"
                />
              </div>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Adding…" : "Add rule"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Active rules</CardTitle>
        </CardHeader>
        <CardContent>
          {rules.isLoading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : rules.data && rules.data.items.length > 0 ? (
            <ul className="divide-y divide-slate-100">
              {rules.data.items.map((r) => (
                <li key={r.id} className="flex items-start justify-between gap-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900">
                      {r.name} <span className="text-xs text-slate-400">({r.type})</span>
                    </p>
                    <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 font-mono text-xs text-slate-600">
                      {JSON.stringify(r.params_json, null, 2)}
                    </pre>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      if (confirm(`Delete rule "${r.name}"?`)) {
                        del.mutate(r.id, { onSuccess: () => toast.success("Deleted") });
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">
              No rules yet. The scheduler will post as soon as anything is ready, with no constraints.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
