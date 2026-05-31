"use client";

import {
  Camera,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  ExternalLink,
  Music2,
  Trash2,
  Tv,
  Users,
} from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { getToken } from "@/lib/api/client";
import {
  useDeleteSocial,
  useOAuthApps,
  useSaveOAuthApp,
  useSocials,
  type OAuthAppStatus,
} from "@/lib/api/hooks";

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

const PLATFORM_META: Record<string, { icon: typeof Tv; color: string }> = {
  youtube: { icon: Tv, color: "text-red-600" },
  meta: { icon: Camera, color: "text-blue-600" },
  tiktok: { icon: Music2, color: "text-pink-600" },
  linkedin: { icon: Users, color: "text-blue-700" },
};

const FIELD_LABELS: Record<string, string> = {
  client_id: "Client ID",
  client_secret: "Client Secret",
  app_id: "App ID",
  app_secret: "App Secret",
  client_key: "Client Key",
};

export default function SocialsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
      <SocialsInner />
    </Suspense>
  );
}

function SocialsInner() {
  const socials = useSocials();
  const oauthApps = useOAuthApps();
  const del = useDeleteSocial();
  const searchParams = useSearchParams();

  useEffect(() => {
    const connected = searchParams.get("connected");
    const error = searchParams.get("error");
    if (connected) {
      toast.success(`${connected} connected!`);
      socials.refetch();
      window.history.replaceState({}, "", "/socials");
    } else if (error) {
      toast.error(`Connection failed: ${error}`);
      window.history.replaceState({}, "", "/socials");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Social Accounts</h1>
        <p className="mt-1 text-sm text-slate-500">
          For each platform: paste your app keys once, then click Connect. Keys + tokens are encrypted at rest.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Platforms</CardTitle>
          <CardDescription>
            Each platform needs a one-time app setup (Client ID + Secret). We show you exactly where to
            get them and which redirect URL to paste.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {oauthApps.isLoading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : (
            oauthApps.data?.map((app) => <PlatformCard key={app.platform} app={app} />)
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Connected accounts</CardTitle>
        </CardHeader>
        <CardContent>
          {socials.isLoading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : socials.data && socials.data.items.length > 0 ? (
            <ul className="divide-y divide-slate-100">
              {socials.data.items.map((s) => {
                const meta = PLATFORM_META[s.platform];
                const Icon = meta?.icon ?? Tv;
                return (
                  <li key={s.id} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <Icon className={`h-5 w-5 ${meta?.color ?? "text-slate-500"}`} />
                      <div>
                        <p className="text-sm font-medium text-slate-900">{s.account_handle}</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {s.platform} · {s.status}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (confirm(`Disconnect ${s.account_handle}?`)) {
                          del.mutate(s.id, {
                            onSuccess: () => toast.success("Disconnected"),
                            onError: () => toast.error("Disconnect failed"),
                          });
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">No accounts connected yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function PlatformCard({ app }: { app: OAuthAppStatus }) {
  const save = useSaveOAuthApp();
  const meta = PLATFORM_META[app.platform];
  const Icon = meta?.icon ?? Tv;

  const [open, setOpen] = useState(!app.configured);
  const [fields, setFields] = useState<Record<string, string>>({});

  function onSave() {
    const missing = app.fields.filter((f) => !fields[f]?.trim());
    if (missing.length) {
      toast.error(`Fill in: ${missing.map((f) => FIELD_LABELS[f] ?? f).join(", ")}`);
      return;
    }
    save.mutate(
      { platform: app.platform, fields },
      {
        onSuccess: (d) => {
          toast.success(d.message);
          setFields({});
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : "Save failed"),
      },
    );
  }

  function startConnect() {
    const token = getToken();
    if (!token) {
      toast.error("Sign in first");
      return;
    }
    window.location.href = `${API_URL}/api/oauth/${app.platform}/connect?token=${encodeURIComponent(token)}`;
  }

  function copyRedirect() {
    navigator.clipboard.writeText(app.redirect_uri);
    toast.success("Redirect URL copied");
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          <Icon className={`h-5 w-5 ${meta?.color ?? "text-slate-500"}`} />
          <div>
            <p className="text-sm font-medium text-slate-900">{app.label}</p>
            <p className="mt-0.5 text-xs">
              {app.configured ? (
                <span className="inline-flex items-center gap-1 text-green-600">
                  <Check className="h-3 w-3" /> App configured
                </span>
              ) : (
                <span className="text-amber-600">Needs app setup</span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={startConnect} disabled={!app.configured} size="sm">
            Connect
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setOpen((v) => !v)}>
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {open && (
        <div className="space-y-4 border-t border-slate-100 p-4">
          <div className="rounded-md bg-slate-50 p-3 text-xs text-slate-600">
            <p>{app.instructions}</p>
            <a
              href={app.console_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex items-center gap-1 font-medium text-blue-600 hover:underline"
            >
              Open developer console <ExternalLink className="h-3 w-3" />
            </a>
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Redirect URL — paste this into the app settings</Label>
            <div className="flex items-center gap-2">
              <code className="flex-1 overflow-x-auto rounded border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs">
                {app.redirect_uri}
              </code>
              <Button variant="outline" size="icon" onClick={copyRedirect}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {app.fields.map((f) => (
              <div key={f} className="space-y-1">
                <Label htmlFor={`${app.platform}-${f}`} className="text-xs">
                  {FIELD_LABELS[f] ?? f}
                </Label>
                <Input
                  id={`${app.platform}-${f}`}
                  type={f.includes("secret") ? "password" : "text"}
                  placeholder={app.configured ? "•••• (saved — leave blank to keep)" : ""}
                  value={fields[f] ?? ""}
                  onChange={(e) => setFields({ ...fields, [f]: e.target.value })}
                />
              </div>
            ))}
          </div>

          <Button onClick={onSave} disabled={save.isPending} size="sm">
            {save.isPending ? "Saving…" : app.configured ? "Update app keys" : "Save app keys"}
          </Button>
        </div>
      )}
    </div>
  );
}
