"use client";

import { CheckCircle2, Plus, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import {
  useCreateCredentials,
  useCredentials,
  useDeleteCredentials,
  useTestCredentials,
} from "@/lib/api/hooks";

const PROVIDER_OPTIONS = [
  { kind: "llm", name: "openai", label: "OpenAI", help: "Used for GPT models. Get one at platform.openai.com/api-keys." },
  { kind: "llm", name: "anthropic", label: "Anthropic", help: "Claude API key (optional v1.1)." },
  { kind: "llm", name: "gemini", label: "Gemini (Google)", help: "Used for Gemini LLM + Nano Banana image generation." },
  { kind: "image", name: "pexels", label: "Pexels", help: "Free stock images. Get a key at pexels.com/api." },
  { kind: "image", name: "unsplash", label: "Unsplash", help: "Free stock images. Get a key at unsplash.com/developers." },
  { kind: "image", name: "nano_banana", label: "Nano Banana", help: "Uses your Gemini API key." },
  { kind: "image", name: "dalle", label: "DALL-E / gpt-image-1", help: "Uses your OpenAI API key." },
  { kind: "voice", name: "elevenlabs", label: "ElevenLabs", help: "Premium voice. Get a key at elevenlabs.io." },
  { kind: "voice", name: "openai_tts", label: "OpenAI TTS", help: "Uses your OpenAI API key (~12× cheaper than ElevenLabs)." },
  { kind: "music", name: "elevenlabs", label: "ElevenLabs Music", help: "Music API requires a paid ElevenLabs plan." },
];

export default function KeysPage() {
  const credentials = useCredentials();
  const create = useCreateCredentials();
  const del = useDeleteCredentials();
  const test = useTestCredentials();

  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    provider_kind: "llm",
    provider_name: "openai",
    label: "default",
    api_key: "",
  });

  function onAdd(e: React.FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        provider_kind: form.provider_kind,
        provider_name: form.provider_name,
        label: form.label,
        payload: { api_key: form.api_key },
      },
      {
        onSuccess: () => {
          toast.success("Key saved (encrypted)");
          setShowAdd(false);
          setForm((f) => ({ ...f, api_key: "" }));
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : "Failed to save";
          toast.error(msg);
        },
      },
    );
  }

  function onTest(id: number, providerName: string) {
    test.mutate(id, {
      onSuccess: (data) => {
        if (data.ok) {
          toast.success(`${providerName}: ${data.message}`);
        } else {
          toast.error(`${providerName}: ${data.message}`);
        }
      },
      onError: () => toast.error(`${providerName}: test failed`),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="mt-1 text-sm text-slate-500">
            Bring your own keys for each AI provider. Keys are encrypted at rest with your master key.
          </p>
        </div>
        <Button onClick={() => setShowAdd((v) => !v)}>
          <Plus className="h-4 w-4" />
          {showAdd ? "Cancel" : "Add key"}
        </Button>
      </div>

      {showAdd && (
        <Card>
          <CardHeader>
            <CardTitle>Add API key</CardTitle>
            <CardDescription>The key is encrypted before it&apos;s stored. Only a 4-character preview is ever shown.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onAdd} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="provider">Provider</Label>
                <select
                  id="provider"
                  value={`${form.provider_kind}/${form.provider_name}`}
                  onChange={(e) => {
                    const [kind, name] = e.target.value.split("/");
                    setForm({ ...form, provider_kind: kind, provider_name: name });
                  }}
                  className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                >
                  {PROVIDER_OPTIONS.map((p) => (
                    <option key={`${p.kind}/${p.name}`} value={`${p.kind}/${p.name}`}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-500">
                  {PROVIDER_OPTIONS.find((p) => p.kind === form.provider_kind && p.name === form.provider_name)?.help}
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="apikey">API key</Label>
                <Input
                  id="apikey"
                  type="password"
                  placeholder="sk-..."
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  required
                />
              </div>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Saving…" : "Save key"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Stored keys</CardTitle>
        </CardHeader>
        <CardContent>
          {credentials.isLoading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : credentials.data && credentials.data.items.length > 0 ? (
            <ul className="divide-y divide-slate-100">
              {credentials.data.items.map((c) => {
                const providerLabel =
                  PROVIDER_OPTIONS.find((p) => p.kind === c.provider_kind && p.name === c.provider_name)?.label ??
                  `${c.provider_kind}/${c.provider_name}`;
                return (
                  <li key={c.id} className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{providerLabel}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {c.label} · <span className="font-mono">{c.secret_preview}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onTest(c.id, providerLabel)}
                        disabled={test.isPending}
                      >
                        {test.isPending ? (
                          "Testing…"
                        ) : (
                          <>
                            <CheckCircle2 className="h-4 w-4" /> Test
                          </>
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          if (confirm(`Delete ${providerLabel} key?`)) {
                            del.mutate(c.id, {
                              onSuccess: () => toast.success("Deleted"),
                              onError: () => toast.error("Delete failed"),
                            });
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <XCircle className="h-10 w-10 text-slate-300" />
              <p className="text-sm text-slate-500">No keys stored yet.</p>
              <p className="text-xs text-slate-400">
                You need at least OpenAI + Pexels + ElevenLabs to run the pipeline.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
