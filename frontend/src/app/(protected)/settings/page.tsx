"use client";

import { Key, Share2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useChangePassword, useMe, useUpdateConfig } from "@/lib/api/hooks";

export default function SettingsPage() {
  const me = useMe();
  const updateConfig = useUpdateConfig();
  const changePassword = useChangePassword();

  // Post limits form state — seeded from server once loaded
  const [shortVideos, setShortVideos] = useState<number>(1);
  const [longVideos, setLongVideos] = useState<number>(1);
  const [limitsSeeded, setLimitsSeeded] = useState(false);

  // Password form state
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");

  useEffect(() => {
    if (me.data && !limitsSeeded) {
      setShortVideos(me.data.daily_short_videos ?? 1);
      setLongVideos(me.data.daily_long_videos ?? 1);
      setLimitsSeeded(true);
    }
  }, [me.data, limitsSeeded]);

  function onSaveLimits(e: React.FormEvent) {
    e.preventDefault();
    updateConfig.mutate(
      { daily_short_videos: shortVideos, daily_long_videos: longVideos },
      {
        onSuccess: () => toast.success("Daily limits saved"),
        onError: (err) => toast.error(err instanceof Error ? err.message : "Save failed"),
      },
    );
  }

  function onChangePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      toast.error("New passwords don't match");
      return;
    }
    changePassword.mutate(
      { current_password: currentPw, new_password: newPw },
      {
        onSuccess: () => {
          toast.success("Password updated");
          setCurrentPw("");
          setNewPw("");
          setConfirmPw("");
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : "Failed"),
      },
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">Configure your account and daily generation limits.</p>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 gap-3">
        <Link
          href="/keys"
          className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
        >
          <Key className="h-4 w-4 text-slate-500" />
          Manage API Keys
        </Link>
        <Link
          href="/socials"
          className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
        >
          <Share2 className="h-4 w-4 text-slate-500" />
          Connect Social Accounts
        </Link>
      </div>

      {/* Daily post limits */}
      <Card>
        <CardHeader>
          <CardTitle>Daily Post Limits</CardTitle>
          <CardDescription>
            How many videos the worker generates and posts automatically each day.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSaveLimits} className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="short-videos">Short videos / day</Label>
                <Input
                  id="short-videos"
                  type="number"
                  min={0}
                  max={50}
                  value={shortVideos}
                  onChange={(e) => setShortVideos(Number(e.target.value))}
                />
                <p className="text-xs text-slate-400">Vertical 9:16 — Instagram Reels, YouTube Shorts, TikTok</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="long-videos">Long videos / day</Label>
                <Input
                  id="long-videos"
                  type="number"
                  min={0}
                  max={20}
                  value={longVideos}
                  onChange={(e) => setLongVideos(Number(e.target.value))}
                />
                <p className="text-xs text-slate-400">Landscape 16:9 — YouTube, Facebook, LinkedIn</p>
              </div>
            </div>
            <Button type="submit" disabled={updateConfig.isPending}>
              {updateConfig.isPending ? "Saving…" : "Save limits"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Change password */}
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onChangePassword} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-pw">Current password</Label>
              <Input
                id="current-pw"
                type="password"
                autoComplete="current-password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-pw">New password</Label>
              <Input
                id="new-pw"
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-pw">Confirm new password</Label>
              <Input
                id="confirm-pw"
                type="password"
                autoComplete="new-password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                required
              />
            </div>
            <Button
              type="submit"
              disabled={changePassword.isPending || !currentPw || !newPw || !confirmPw}
            >
              {changePassword.isPending ? "Updating…" : "Update password"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Account info */}
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Row label="Email">{me.data?.email ?? "—"}</Row>
          <Row label="Role">{me.data?.role ?? "—"}</Row>
          <Row label="Tenant">{me.data?.tenant_name ?? "—"}</Row>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{children}</span>
    </div>
  );
}
