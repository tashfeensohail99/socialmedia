"use client";

import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useUsageSummary } from "@/lib/api/hooks";
import { formatCurrency } from "@/lib/utils";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function UsagePage() {
  const [month, setMonth] = useState(currentMonth());
  const usage = useUsageSummary(month);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Cost &amp; Usage</h1>
          <p className="mt-1 text-sm text-slate-500">
            Every API call your pipeline makes is logged here with the computed cost.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="month">Month</Label>
          <Input
            id="month"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="w-40"
          />
        </div>
      </div>

      {usage.isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : usage.data ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Tile label="Total events" value={String(usage.data.total_events)} />
            <Tile label="Total spend" value={formatCurrency(usage.data.total_cost_usd)} />
            <Tile label="Month" value={usage.data.month} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Breakdown by provider/model</CardTitle>
              <CardDescription>Sorted by cost descending.</CardDescription>
            </CardHeader>
            <CardContent>
              {usage.data.by_provider_model.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                      <th className="py-2">Provider / Model</th>
                      <th className="py-2 text-right">Calls</th>
                      <th className="py-2 text-right">Tokens in</th>
                      <th className="py-2 text-right">Tokens out</th>
                      <th className="py-2 text-right">Units</th>
                      <th className="py-2 text-right">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.data.by_provider_model.map((r) => (
                      <tr key={`${r.provider}-${r.model}`} className="border-b border-slate-100">
                        <td className="py-2 font-mono text-xs">
                          {r.provider} / {r.model}
                        </td>
                        <td className="py-2 text-right">{r.calls}</td>
                        <td className="py-2 text-right text-slate-500">
                          {r.tokens_in ? r.tokens_in.toLocaleString() : "—"}
                        </td>
                        <td className="py-2 text-right text-slate-500">
                          {r.tokens_out ? r.tokens_out.toLocaleString() : "—"}
                        </td>
                        <td className="py-2 text-right text-slate-500">{r.units || "—"}</td>
                        <td className="py-2 text-right font-medium">{formatCurrency(r.cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="py-6 text-center text-sm text-slate-500">No events recorded for {month}.</p>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{value}</p>
    </div>
  );
}
