"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, setToken } from "@/lib/api/client";
import { useLogin } from "@/lib/api/hooks";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const login = useLogin({
    onSuccess: (data) => {
      setToken(data.access_token);
      toast.success(`Welcome back, ${data.role}`);
      router.replace("/dashboard");
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          toast.error("Invalid email or password");
        } else if (err.status >= 500) {
          toast.error("Backend error", {
            description: `The API returned ${err.status}. Check the uvicorn log.`,
          });
        } else {
          toast.error(`Login failed (${err.status})`, { description: err.message });
        }
      } else {
        // Network error — backend probably not running.
        toast.error("Cannot reach the backend", {
          description: `Tried ${apiUrl}/api/auth/login. Is uvicorn running on port 8000?`,
          duration: 10_000,
        });
      }
    },
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    login.mutate({ email, password });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in to Summit Automates</CardTitle>
          <CardDescription>Welcome back. Enter your credentials to continue.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={login.isPending || !email || !password}
            >
              {login.isPending ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-center text-sm text-slate-600">
              Don&apos;t have an account?{" "}
              <Link href="/signup" className="font-medium text-blue-600 hover:underline">
                Start a free trial
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
