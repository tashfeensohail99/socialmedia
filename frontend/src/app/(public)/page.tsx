import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div>
      {/* Hero */}
      <section className="border-b border-slate-100 bg-gradient-to-b from-white to-slate-50">
        <div className="mx-auto max-w-5xl px-6 py-24 sm:py-32">
          <div className="max-w-2xl">
            <p className="text-sm font-medium uppercase tracking-wider text-blue-600">
              Summit Automates
            </p>
            <h1 className="mt-3 text-4xl font-bold leading-tight tracking-tight text-slate-900 sm:text-5xl">
              AI that researches, writes, films, and posts your social videos —
              while you sleep.
            </h1>
            <p className="mt-5 text-lg leading-relaxed text-slate-600">
              One configurable engine that discovers topics for your niche,
              generates vertical short videos and YouTube long-form, then posts
              them to Instagram, Facebook, YouTube, TikTok, and LinkedIn on the
              schedule you set. Bring your own AI keys; we never touch your
              social passwords.
            </p>
            <div className="mt-8 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
              <Link href="/signup">
                <Button size="lg">Start your free 7-day trial</Button>
              </Link>
              <span className="text-sm text-slate-500">
                Already have an account?{" "}
                <Link
                  href="/login"
                  className="font-medium text-blue-600 hover:underline"
                >
                  Sign in
                </Link>
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <h2 className="text-2xl font-bold text-slate-900">How it works</h2>
        <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <Step
            n={1}
            title="Define your niche"
            body="Write your content niche, tone, audience, and forbidden topics once. The engine threads these into every prompt."
          />
          <Step
            n={2}
            title="Bring your AI keys"
            body="Paste in your own OpenAI, ElevenLabs, and Pexels keys. They live encrypted in your workspace. We never carry your AI bill."
          />
          <Step
            n={3}
            title="Connect your socials"
            body="One-click OAuth into Instagram, Facebook, YouTube, TikTok, and LinkedIn. Posty stores only revocable tokens."
          />
          <Step
            n={4}
            title="Let it run"
            body="The engine discovers fresh topics, scripts a narrative, generates images + voiceover, assembles a video, and posts it on your schedule."
          />
        </div>
      </section>

      {/* Trust */}
      <section className="border-y border-slate-100 bg-slate-50">
        <div className="mx-auto max-w-5xl px-6 py-16">
          <h2 className="text-2xl font-bold text-slate-900">
            Built for operators who care about control
          </h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <Trust
              title="Your keys, your costs"
              body="BYOK means we don't mark up your AI bills. The cost dashboard shows exactly what every post costs in OpenAI / ElevenLabs / Pexels usage."
            />
            <Trust
              title="Encrypted at rest"
              body="API keys and social OAuth tokens are encrypted with Fernet (AES-128-CBC + HMAC). We never log a plaintext key."
            />
            <Trust
              title="Preview before publish"
              body="Generated posts land in a queue. Review the caption, video, and hashtags before they go live — or let the scheduler run autonomous."
            />
            <Trust
              title="Per-niche prompts"
              body="Every word in every prompt is editable. The engine ships with strong defaults; you can fork them per niche from the admin panel."
            />
            <Trust
              title="Multi-platform formats"
              body="Vertical 9:16 for Reels / Shorts / TikTok. Horizontal 16:9 with Ken Burns for YouTube long-form and LinkedIn. One pipeline, two outputs."
            />
            <Trust
              title="Self-served setup"
              body="A guided wizard walks you from zero to first published post in under 30 minutes. No engineer required."
            />
          </div>
        </div>
      </section>

      {/* CTA + legal */}
      <section className="mx-auto max-w-5xl px-6 py-20 text-center">
        <h2 className="text-2xl font-bold text-slate-900">Ready to try it?</h2>
        <p className="mx-auto mt-3 max-w-xl text-slate-600">
          Spin up a workspace in 30 seconds. No credit card required for the
          first 7 days.
        </p>
        <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/signup">
            <Button size="lg">Start free trial</Button>
          </Link>
          <a
            href="mailto:admin@summitautomates.com?subject=Question%20about%20Summit%20Automates"
            className="text-sm text-slate-600 hover:text-slate-900"
          >
            or email us at admin@summitautomates.com
          </a>
        </div>
      </section>
    </div>
  );
}

function Step({ n, title, body }: { n: number; title: string; body: string }) {
  return (
    <div>
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
        {n}
      </div>
      <h3 className="mt-4 text-base font-semibold text-slate-900">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{body}</p>
    </div>
  );
}

function Trust({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{body}</p>
    </div>
  );
}
