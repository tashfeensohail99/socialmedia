"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, setToken } from "@/lib/api/client";
import { useSignup } from "@/lib/api/hooks";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");

  const signup = useSignup({
    onSuccess: (data) => {
      setToken(data.access_token);
      toast.success("Welcome to Summit Automates!", {
        description: "Your 7-day free trial is active.",
      });
      router.replace("/dashboard");
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          toast.error("Email already in use", {
            description: "Try signing in instead, or use a different email.",
          });
        } else if (err.status === 422) {
          toast.error("Please check your details", {
            description: "Password must be at least 8 characters.",
          });
        } else if (err.status >= 500) {
          toast.error("Backend error", {
            description: `The API returned ${err.status}.`,
          });
        } else {
          toast.error(`Signup failed (${err.status})`, { description: err.message });
        }
      } else {
        toast.error("Cannot reach the server", {
          description: "Check your internet connection and try again.",
          duration: 10_000,
        });
      }
    },
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    signup.mutate({ email, password, workspace_name: workspaceName });
  }

  const passwordTooShort = password.length > 0 && password.length < 8;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Start your free trial</CardTitle>
          <CardDescription>
            7 days free. No credit card required.
          </CardDescription>
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
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
              <p
                className={`text-xs ${passwordTooShort ? "text-red-600" : "text-slate-500"}`}
              >
                At least 8 characters.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="workspaceName">Workspace name (optional)</Label>
              <Input
                id="workspaceName"
                type="text"
                placeholder="My agency"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                maxLength={128}
              />
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={
                signup.isPending || !email || password.length < 8
              }
            >
              {signup.isPending ? "Creating your workspace…" : "Create account"}
            </Button>
            <p className="text-center text-xs text-slate-500">
              By signing up you agree to our{" "}
              <Link href="/terms" className="underline hover:text-slate-700">
                Terms
              </Link>{" "}
              and{" "}
              <Link href="/privacy" className="underline hover:text-slate-700">
                Privacy Policy
              </Link>
              .
            </p>
            <p className="text-center text-sm text-slate-600">
              Already have an account?{" "}
              <Link href="/login" className="font-medium text-blue-600 hover:underline">
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
