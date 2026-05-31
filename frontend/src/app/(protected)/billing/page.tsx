"use client";

import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useMe } from "@/lib/api/hooks";

const STATUS_LABELS: Record<string, { label: string; tone: string }> = {
  none: { label: "No subscription", tone: "bg-slate-100 text-slate-700" },
  trialing: { label: "Trial", tone: "bg-blue-100 text-blue-700" },
  active: { label: "Active", tone: "bg-green-100 text-green-700" },
  past_due: { label: "Payment failed", tone: "bg-amber-100 text-amber-700" },
  cancelled: { label: "Cancelled", tone: "bg-red-100 text-red-700" },
};

export default function BillingPage() {
  const me = useMe();
  const status = me.data?.subscription_status ?? "none";
  const pill = STATUS_LABELS[status] ?? STATUS_LABELS.none;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Billing</h1>
        <p className="mt-1 text-sm text-slate-500">
          Your subscription is managed by Whop. Click below to update payment, change plans, or cancel.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Current subscription</CardTitle>
          <CardDescription>Status updates within minutes of any change on Whop.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${pill.tone}`}>
              {pill.label}
            </span>
            {me.data?.tenant_name && (
              <span className="text-sm text-slate-500">Workspace: {me.data.tenant_name}</span>
            )}
          </div>

          {status === "cancelled" && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              Your subscription is cancelled. Your workspace data will be permanently deleted in
              30 days unless you resubscribe.
            </div>
          )}
          {status === "past_due" && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              We couldn&apos;t collect your last payment. Update your payment method on Whop to
              keep your workspace active.
            </div>
          )}

          <div className="pt-2">
            <a href="https://whop.com/orders" target="_blank" rel="noreferrer">
              <Button>
                <ExternalLink className="h-4 w-4" />
                Open Whop dashboard
              </Button>
            </a>
            <p className="mt-2 text-xs text-slate-500">
              On Whop you can update payment, change plans, cancel, or view invoices.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Need help?</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-600">
            Billing questions, refund requests, or account issues:{" "}
            <a href="mailto:admin@summitautomates.com" className="font-medium text-blue-600 underline">
              admin@summitautomates.com
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
