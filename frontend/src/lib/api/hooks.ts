/**
 * Thin TanStack Query hooks per resource. Each hook is fully typed against the
 * generated OpenAPI types and centralizes query keys + cache invalidation.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { api, type paths } from "@/lib/api/client";

// ─── Type helpers — pull request/response shapes out of the OpenAPI types ──

type Resp200<P extends keyof paths, M extends keyof paths[P]> = paths[P][M] extends {
  responses: { 200: { content: { "application/json": infer T } } };
}
  ? T
  : never;

type Resp201<P extends keyof paths, M extends keyof paths[P]> = paths[P][M] extends {
  responses: { 201: { content: { "application/json": infer T } } };
}
  ? T
  : never;

type Body<P extends keyof paths, M extends keyof paths[P]> = paths[P][M] extends {
  requestBody: { content: { "application/json": infer T } };
}
  ? T
  : never;

// ─── Query keys ─────────────────────────────────────────────────────────────

export const qk = {
  me: ["me"] as const,
  niches: (params?: object) => ["niches", params] as const,
  niche: (id: number) => ["niche", id] as const,
  credentials: ["credentials"] as const,
  socials: ["socials"] as const,
  topics: (params?: object) => ["topics", params] as const,
  topicSources: ["topic-sources"] as const,
  posts: (params?: object) => ["posts", params] as const,
  post: (id: number) => ["post", id] as const,
  schedules: (params?: object) => ["schedules", params] as const,
  postingRules: ["posting-rules"] as const,
  prompts: ["prompts"] as const,
  usage: (month?: string) => ["usage", month] as const,
};

// ─── Auth ──────────────────────────────────────────────────────────────────

export type LoginResponse = Resp200<"/api/auth/login", "post">;
export type LoginBody = Body<"/api/auth/login", "post">;

export function useLogin(opts?: UseMutationOptions<LoginResponse, Error, LoginBody>) {
  return useMutation({
    mutationFn: (body: LoginBody) =>
      api<LoginResponse>("/api/auth/login", { method: "POST", body, unauthenticated: true }),
    ...opts,
  });
}

// Signup uses the same TokenResponse as login but at a different endpoint.
// The backend returns 201 Created so we pull from Resp201.
export type SignupResponse = Resp201<"/api/auth/signup", "post">;
export type SignupBody = Body<"/api/auth/signup", "post">;

export function useSignup(opts?: UseMutationOptions<SignupResponse, Error, SignupBody>) {
  return useMutation({
    mutationFn: (body: SignupBody) =>
      api<SignupResponse>("/api/auth/signup", { method: "POST", body, unauthenticated: true }),
    ...opts,
  });
}

// ─── Me ────────────────────────────────────────────────────────────────────

export type Me = Resp200<"/api/me", "get">;

export function useMe(opts?: Partial<UseQueryOptions<Me>>) {
  return useQuery({
    queryKey: qk.me,
    queryFn: () => api<Me>("/api/me"),
    retry: false,
    staleTime: 30_000,
    ...opts,
  });
}

export interface ConfigUpdate {
  daily_short_videos: number;
  daily_long_videos: number;
}

export function useUpdateConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ConfigUpdate) =>
      api<Me>("/api/me/config", { method: "PATCH", body }),
    onSuccess: (data) => qc.setQueryData(qk.me, data),
  });
}

export interface ChangePasswordBody {
  current_password: string;
  new_password: string;
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: ChangePasswordBody) =>
      api<{ message: string }>("/api/me/change-password", { method: "POST", body }),
  });
}

// ─── Automation ──────────────────────────────────────────────────────────────

export function useRunAutomation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api<{ message: string }>("/api/automation/run-now", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["posts"] });
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

// ─── Niches ────────────────────────────────────────────────────────────────

export type NichesList = Resp200<"/api/niches", "get">;
export type Niche = Resp200<"/api/niches/{niche_id}", "get">;
export type NicheCreate = Body<"/api/niches", "post">;
export type NicheUpdate = Body<"/api/niches/{niche_id}", "patch">;

export function useNiches(opts?: Partial<UseQueryOptions<NichesList>>) {
  return useQuery({
    queryKey: qk.niches(),
    queryFn: () => api<NichesList>("/api/niches"),
    ...opts,
  });
}

export function useNiche(id: number | null, opts?: Partial<UseQueryOptions<Niche>>) {
  return useQuery({
    queryKey: qk.niche(id ?? 0),
    queryFn: () => api<Niche>(`/api/niches/${id}`),
    enabled: id !== null && id !== undefined && id > 0,
    ...opts,
  });
}

export function useCreateNiche() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NicheCreate) =>
      api<Resp201<"/api/niches", "post">>("/api/niches", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["niches"] }),
  });
}

export function useUpdateNiche(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NicheUpdate) =>
      api<Niche>(`/api/niches/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["niches"] });
      qc.invalidateQueries({ queryKey: qk.niche(id) });
    },
  });
}

export function useDeleteNiche() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api(`/api/niches/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["niches"] }),
  });
}

// AI niche drafting — turn a free-text business description into a structured niche.
export interface NicheDraft {
  name: string;
  description: string;
  target_audience: string;
  tone: string;
  content_pillars: string[];
  forbidden_topics: string[];
  hashtag_seeds: string[];
  cta: string;
  news_search_query: string;
}

export function useDraftNiche() {
  return useMutation({
    mutationFn: (business_description: string) =>
      api<NicheDraft>("/api/niches/draft-from-description", {
        method: "POST",
        body: { business_description },
      }),
  });
}

// ─── Credentials ───────────────────────────────────────────────────────────

export type CredentialsList = Resp200<"/api/credentials", "get">;
export type CredentialsCreate = Body<"/api/credentials", "post">;

export function useCredentials() {
  return useQuery({
    queryKey: qk.credentials,
    queryFn: () => api<CredentialsList>("/api/credentials"),
  });
}

export function useCreateCredentials() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CredentialsCreate) =>
      api("/api/credentials", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.credentials }),
  });
}

export function useDeleteCredentials() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api(`/api/credentials/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.credentials }),
  });
}

export type CredentialsTestResult = Resp200<"/api/credentials/{cred_id}/test", "post">;

export function useTestCredentials() {
  return useMutation({
    mutationFn: (id: number) =>
      api<CredentialsTestResult>(`/api/credentials/${id}/test`, { method: "POST" }),
  });
}

// ─── Social accounts ───────────────────────────────────────────────────────

export type SocialsList = Resp200<"/api/social-accounts", "get">;

export function useSocials() {
  return useQuery({
    queryKey: qk.socials,
    queryFn: () => api<SocialsList>("/api/social-accounts"),
  });
}

export function useDeleteSocial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api(`/api/social-accounts/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.socials }),
  });
}

// OAuth app credentials (Client ID / Secret entered in the UI)
export interface OAuthAppStatus {
  platform: string;
  label: string;
  configured: boolean;
  fields: string[];
  console_url: string;
  instructions: string;
  redirect_uri: string;
}

export function useOAuthApps() {
  return useQuery({
    queryKey: ["oauth-apps"],
    queryFn: () => api<OAuthAppStatus[]>("/api/social-accounts/oauth-apps/status"),
  });
}

export function useSaveOAuthApp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ platform, fields }: { platform: string; fields: Record<string, string> }) =>
      api<{ message: string }>(`/api/social-accounts/oauth-apps/${platform}`, {
        method: "PUT",
        body: fields,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["oauth-apps"] }),
  });
}

// ─── Posts ─────────────────────────────────────────────────────────────────

export type PostsList = Resp200<"/api/posts", "get">;
export type Post = Resp200<"/api/posts/{post_id}", "get">;

export function usePosts(filters?: { status?: string; niche_id?: number; video_format?: string }) {
  return useQuery({
    queryKey: qk.posts(filters),
    queryFn: () => api<PostsList>("/api/posts", { query: filters as Record<string, string | number> }),
  });
}

export function usePost(id: number | null) {
  return useQuery({
    queryKey: qk.post(id ?? 0),
    queryFn: () => api<Post>(`/api/posts/${id}`),
    enabled: id !== null && id !== undefined && id > 0,
  });
}

export type RunPipelineBody = Body<"/api/posts/run", "post">;
export type RunPipelineResp = Resp201<"/api/posts/run", "post">;

export function useRunPipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RunPipelineBody) =>
      api<RunPipelineResp>("/api/posts/run", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  });
}

export function useRegeneratePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api(`/api/posts/${id}/regenerate`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  });
}

export type PostNowBody = Body<"/api/posts/{post_id}/post-now", "post">;
export type PostNowResp = Resp200<"/api/posts/{post_id}/post-now", "post">;

export function usePostNow(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PostNowBody) =>
      api<PostNowResp>(`/api/posts/${id}/post-now`, { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.post(id) });
      qc.invalidateQueries({ queryKey: ["posts"] });
    },
  });
}

export function useDeletePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api(`/api/posts/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  });
}

// ─── Schedules ─────────────────────────────────────────────────────────────

export type SchedulesList = Resp200<"/api/schedules", "get">;
export type ScheduleCreate = Body<"/api/schedules", "post">;

export function useSchedules(filters?: { status?: string }) {
  return useQuery({
    queryKey: qk.schedules(filters),
    queryFn: () => api<SchedulesList>("/api/schedules", { query: filters as Record<string, string> }),
  });
}

export function useCreateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ScheduleCreate) =>
      api("/api/schedules", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useCancelSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api(`/api/schedules/${id}/cancel`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

// ─── Topics ────────────────────────────────────────────────────────────────

export type TopicsList = Resp200<"/api/topics", "get">;
export type TopicCreate = Body<"/api/topics", "post">;

export function useTopics(filters?: { status?: string; min_score?: number }) {
  return useQuery({
    queryKey: qk.topics(filters),
    queryFn: () => api<TopicsList>("/api/topics", { query: filters as Record<string, string | number> }),
  });
}

export function useCreateTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TopicCreate) =>
      api("/api/topics", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}

export function useRejectTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api(`/api/topics/${id}/reject`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}

export function usePromoteTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api(`/api/topics/${id}/promote`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}

// ─── Topic sources ─────────────────────────────────────────────────────────

export type TopicSourcesList = Resp200<"/api/topic-sources", "get">;
export type TopicSourceCreate = Body<"/api/topic-sources", "post">;

export function useTopicSources() {
  return useQuery({
    queryKey: qk.topicSources,
    queryFn: () => api<TopicSourcesList>("/api/topic-sources"),
  });
}

export function useCreateTopicSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TopicSourceCreate) =>
      api("/api/topic-sources", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.topicSources }),
  });
}

export function useRunTopicSourceNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api(`/api/topic-sources/${id}/run-now`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.topicSources });
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}

// ─── Posting rules ─────────────────────────────────────────────────────────

export type PostingRulesList = Resp200<"/api/posting-rules", "get">;
export type PostingRuleCreate = Body<"/api/posting-rules", "post">;

export function usePostingRules() {
  return useQuery({
    queryKey: qk.postingRules,
    queryFn: () => api<PostingRulesList>("/api/posting-rules"),
  });
}

export function useCreatePostingRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PostingRuleCreate) =>
      api("/api/posting-rules", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.postingRules }),
  });
}

export function useDeletePostingRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api(`/api/posting-rules/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.postingRules }),
  });
}

// ─── Prompt templates ──────────────────────────────────────────────────────

export type PromptsList = Resp200<"/api/prompt-templates", "get">;
export type PromptUpsert = Body<"/api/prompt-templates/{slug}", "put">;

export function usePrompts() {
  return useQuery({
    queryKey: qk.prompts,
    queryFn: () => api<PromptsList>("/api/prompt-templates"),
  });
}

export function useUpsertPrompt(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PromptUpsert) =>
      api(`/api/prompt-templates/${slug}`, { method: "PUT", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.prompts }),
  });
}

// ─── Usage summary ─────────────────────────────────────────────────────────

export type UsageSummary = Resp200<"/api/usage/summary", "get">;

export function useUsageSummary(month?: string) {
  return useQuery({
    queryKey: qk.usage(month),
    queryFn: () => api<UsageSummary>("/api/usage/summary", { query: { month } }),
  });
}
