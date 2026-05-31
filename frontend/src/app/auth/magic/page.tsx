"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api, setToken } from "@/lib/api/client";

interface MagicLoginResponse {
  access_token: string;
  user_id: number;
  tenant_id: number;
  role: string;
}

function MagicLoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");
  const ran = useRef(false);
  const [status, setStatus] = useState<"working" | "ok" | "fail">("working");
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    if (!token) {
      setStatus("fail");
      setErrorMsg("No token in the URL. Check that you clicked the full link from your email.");
      return;
    }
    api<MagicLoginResponse>("/api/auth/magic-login", {
      method: "POST",
      body: { token },
      unauthenticated: true,
    })
      .then((res) => {
        setToken(res.access_token);
        setStatus("ok");
        router.replace("/dashboard");
      })
      .catch((err) => {
        setStatus("fail");
        if (err instanceof ApiError) {
          setErrorMsg(err.message || "This link is no longer valid.");
        } else {
          setErrorMsg("Couldn't reach the server. Try again in a minute.");
        }
      });
  }, [token, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
            {status === "working" && "Signing you in…"}
            {status === "ok" && "Signed in"}
            {status === "fail" && "We couldn't sign you in"}
          </CardTitle>
          <CardDescription>
            {status === "working" && "Hold tight — exchanging your magic link for a session."}
            {status === "ok" && "Redirecting to your dashboard."}
            {status === "fail" && errorMsg}
          </CardDescription>
        </CardHeader>
        {status === "fail" && (
          <CardContent>
            <p className="text-sm text-slate-600">
              Magic links expire after 30 minutes. If yours has expired, contact{" "}
              <a href="mailto:admin@summitautomates.com" className="font-medium text-blue-600 underline">
                admin@summitautomates.com
              </a>{" "}
              to get a fresh link.
            </p>
            <div className="mt-4 flex gap-2">
              <Button onClick={() => router.push("/login")}>Go to sign-in</Button>
              <Button variant="outline" onClick={() => router.push("/")}>
                Back to home
              </Button>
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}

export default function MagicLoginPage() {
  // useSearchParams requires being inside Suspense in Next.js 15+.
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-100">
          <p className="text-sm text-slate-500">Loading…</p>
        </div>
      }
    >
      <MagicLoginInner />
    </Suspense>
  );
}
