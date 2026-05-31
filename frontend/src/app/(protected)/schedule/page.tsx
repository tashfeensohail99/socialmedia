"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useCancelSchedule, useSchedules } from "@/lib/api/hooks";
import { formatRelativeDate } from "@/lib/utils";

export default function SchedulePage() {
  const schedules = useSchedules();
  const cancel = useCancelSchedule();

  // Group schedules by date for a simple calendar-ish view.
  const grouped = new Map<string, Array<NonNullable<typeof schedules.data>["items"][number]>>();
  for (const s of schedules.data?.items ?? []) {
    const day = new Date(s.scheduled_for_utc).toLocaleDateString();
    if (!grouped.has(day)) grouped.set(day, []);
    grouped.get(day)!.push(s);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Schedule</h1>
        <p className="mt-1 text-sm text-slate-500">
          Posts queued for future publishing. The worker processes due schedules every 60 seconds.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>How scheduling works</CardTitle>
          <CardDescription>
            Open a Post and click &quot;Schedule&quot; to add it here. The worker will dispatch posting attempts to the listed
            platforms at the scheduled time.
          </CardDescription>
        </CardHeader>
      </Card>

      {schedules.isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : schedules.data && schedules.data.items.length > 0 ? (
        <div className="space-y-4">
          {Array.from(grouped.entries()).map(([day, items]) => (
            <Card key={day}>
              <CardHeader>
                <CardTitle className="text-base">{day}</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="divide-y divide-slate-100">
                  {items.map((s) => (
                    <li key={s.id} className="flex items-center justify-between py-3">
                      <div>
                        <Link href={`/posts/${s.post_id}`} className="text-sm font-medium hover:underline">
                          Post #{s.post_id}
                        </Link>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {new Date(s.scheduled_for_utc).toLocaleTimeString()} · {s.status} · {(s.platforms_json || []).join(", ")}
                          {s.attempts_count > 0 && ` · ${s.attempts_count} attempt(s)`}
                        </p>
                      </div>
                      {s.status === "pending" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            cancel.mutate(s.id, {
                              onSuccess: () => toast.success("Cancelled"),
                              onError: () => toast.error("Cancel failed"),
                            })
                          }
                        >
                          <X className="h-4 w-4" /> Cancel
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-10 text-center text-sm text-slate-500">
            No scheduled posts. Open a ready Post and click &quot;Schedule&quot; to queue one up.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
