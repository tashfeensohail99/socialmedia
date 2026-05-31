# OAuth Review Submission Kit — Summit Automates

Everything you need to file the four OAuth app reviews in parallel. Each
platform's review form asks the same kinds of questions; this kit gives you
copy-paste-ready answers tuned to Summit Automates' actual functionality.

**Submit ASAP.** The platforms take wildly different amounts of time:

| Platform | Typical review time | Difficulty |
|---|---|---|
| LinkedIn | 3–7 days | Easy |
| Google | 1–3 weeks | Medium |
| Meta (FB + IG) | 2–4 weeks | Hard — business verification + demo video |
| TikTok | 2–8 weeks | Hardest — often legal review |

---

## Production topology — IMPORTANT

The product runs across **three subdomains**. Don't mix them up when filling
in the review forms:

| Subdomain | What it is | Used for |
|---|---|---|
| `summitautomates.com` | Marketing site (separate repo) | "Application home page" / "Website" fields |
| `app.summitautomates.com` | SaaS frontend (Next.js) | Legal URLs, reviewer login/signup, demo screencast |
| `api.summitautomates.com` | SaaS backend (FastAPI) | **OAuth redirect/callback URLs only** |

## Prerequisites — all live as of this deploy ✅

These four URLs are publicly reachable over HTTPS (verified — Let's Encrypt
certs valid):

| URL | Purpose | Status |
|---|---|---|
| `https://summitautomates.com/` | Marketing landing page | ✅ live |
| `https://app.summitautomates.com/terms` | Terms of Service | ✅ live (200) |
| `https://app.summitautomates.com/privacy` | Privacy Policy | ✅ live (200) |
| `https://app.summitautomates.com/data-deletion` | Data Deletion Instructions (Meta-required) | ✅ live (200) |

The legal entity placeholders are already filled in: **Summit Systems
(Private) Limited**, Corporate UIN 0324466, registered office Office # 3,
First Floor, Mughal Market, Al-Rehman Arcade, Sector G-13/2, Islamabad,
Pakistan. Governing law: Islamabad, Pakistan.

### OAuth redirect/callback URLs (production) — copy exactly

These live on the **api** subdomain (the FastAPI backend). Register the
matching one in each platform's developer console:

| Platform | Redirect / Callback URL |
|---|---|
| Meta (FB + IG) | `https://api.summitautomates.com/api/oauth/meta/callback` |
| Google (YouTube) | `https://api.summitautomates.com/api/oauth/youtube/callback` |
| TikTok | `https://api.summitautomates.com/api/oauth/tiktok/callback` |
| LinkedIn | `https://api.summitautomates.com/api/oauth/linkedin/callback` |

---

## Shared answers — use these for every platform

### Company / app identity

- **Product name**: Summit Automates
- **Legal entity**: Summit Systems (Private) Limited (Pakistan, Corporate UIN 0324466)
- **Marketing domain**: summitautomates.com
- **App domain**: app.summitautomates.com
- **API domain**: api.summitautomates.com
- **App description (one-line)**: AI that researches, writes, films, and schedules social videos for niche operators.
- **App description (longer)**:
  > Summit Automates is a SaaS tool that helps individual creators and small businesses publish consistent social-media video content. The user defines a content niche, brings their own AI provider keys (OpenAI, ElevenLabs, etc.), and connects the social accounts they own. Our pipeline discovers relevant topics, scripts a narrative, generates scene images and voiceover, assembles a vertical or horizontal video, and publishes it to the user's connected accounts on a schedule the user controls. The user reviews and approves the schedule; we never auto-create content on accounts the user did not connect.
- **Category**: Productivity / Marketing
- **Industry**: Software-as-a-Service (SaaS)
- **Business model**: Subscription via Whop (merchant of record)
- **Support email**: admin@summitautomates.com

### Test credentials for reviewers

You'll need to create a **demo workspace** with realistic data, plus **demo
social accounts** the reviewer can log into. Set these up once, share them
with every platform.

| Item | Value (fill in before submitting) |
|---|---|
| Reviewer signup/login URL | `https://app.summitautomates.com/login` (self-serve signup at `/signup`) |
| Reviewer test login (admin panel) | `reviewer@summitautomates.com` / `[strong password]` |
| Demo Instagram Business account | `@summit_demo` (you create) |
| Demo Facebook Page | "Summit Demo" |
| Demo YouTube channel | "Summit Demo" |
| Demo TikTok account | `@summit_demo` |
| Demo LinkedIn page or member account | Your own member account |

Tip: name them all `summit_demo` or similar so reviewers immediately
understand they're test fixtures.

---

## A. Meta App Review (Facebook + Instagram)

**Where**: developers.facebook.com → Your App → App Review → Permissions and Features

**App configuration**:

| Field | Value |
|---|---|
| App name | Summit Automates |
| App contact email | admin@summitautomates.com |
| App domains | summitautomates.com, app.summitautomates.com, api.summitautomates.com |
| Privacy policy URL | https://app.summitautomates.com/privacy |
| Terms of service URL | https://app.summitautomates.com/terms |
| User data deletion | https://app.summitautomates.com/data-deletion (callback URL for now — see note below) |
| Category | Business |
| OAuth redirect URI | https://api.summitautomates.com/api/oauth/meta/callback |

### Permissions to request

For Facebook Pages:
- `pages_show_list` — list the user's Pages so they can pick which to connect
- `pages_read_engagement` — required by Meta to verify the user manages the Page
- `pages_manage_posts` — publish video posts to the Page
- `business_management` — required by Meta when paired with the above

For Instagram (Business / Creator accounts attached to a connected Page):
- `instagram_basic` — basic read access
- `instagram_content_publish` — publish videos via the Instagram Graph API

### Use-case justifications (paste these per permission)

**`pages_manage_posts`** — what to write:
> Summit Automates is a self-serve SaaS for creators who manage their own
> Facebook Pages. After a user signs in to our app and connects a Page they
> own, our pipeline generates a video and publishes it on the schedule the
> user specifies. The user retains full edit control — every generated post
> appears in a review queue with the caption and video preview before it
> publishes. Without `pages_manage_posts` the user would have to manually
> upload each generated video to their Page, defeating the purpose of
> automation. The permission is used only for posts the user has explicitly
> queued in our admin panel.

**`instagram_content_publish`** — same template, replace "Page" with
"Instagram Business / Creator account".

### Demo screencast script (3–5 min, required)

Record this in OBS / Loom and upload during submission:

1. **00:00 — Intro (10s)**: "This is Summit Automates, a content automation
   tool for social media operators. I'm going to show you how a user
   connects their Facebook Page and Instagram account, generates a video, and
   publishes it."
2. **00:10 — Sign in (15s)**: Show the admin panel login at `/login`. Sign
   in with the reviewer test account.
3. **00:25 — Dashboard (10s)**: Show the empty dashboard with the sidebar.
4. **00:35 — Add API keys (30s)**: Go to `/keys`. Add an OpenAI key, a
   Pexels key, and an ElevenLabs key. Show the "Test" button verifying
   they work. Emphasize: "Keys are encrypted at rest."
5. **01:05 — Connect Facebook + Instagram (45s)**: Go to `/socials`. Click
   the "Facebook + Instagram" button. Walk through the Facebook OAuth
   consent screen. Show the Pages list and pick the demo Page. Show that
   Summit lists the connected Page and the linked Instagram Business
   account.
6. **01:50 — Create a niche (45s)**: Go to `/niches`. Click "New niche".
   Fill in: name = "Demo fitness tips", description = "5-minute desk
   workouts for office workers", target audience = "office workers", tone
   = "friendly". Save.
7. **02:35 — Generate a post (60s)**: Go to `/posts`. Click "Generate post".
   Pick the niche. Set topic title = "3 desk stretches that fix posture in
   60 seconds". Click Generate. Skip ahead through the loading state.
   When done, click into the new post to show the caption, hashtags, and
   video preview.
8. **03:35 — Post to Facebook + Instagram (30s)**: Click "Post Now". Pick
   "facebook" and "instagram". Click Post. Show the success toast.
9. **04:05 — Verify on the platform (30s)**: Open Facebook in a new tab,
   show the post live on the connected Page. Open Instagram, show the
   Reel.
10. **04:35 — Show data deletion (15s)**: Go to `/socials`, click the trash
    icon next to the Instagram account, confirm the disconnect.
11. **04:50 — Wrap (10s)**: "That's the full flow — user-driven, every
    post reviewed before publishing, instant disconnect from the admin
    panel."

### Business verification

Meta requires business verification for the publishing permissions. You
need to submit:
- Business name (your LLC)
- Business address
- Business email at the domain (`admin@summitautomates.com` ✓)
- Business website (summitautomates.com ✓)
- Tax ID or registration number

If your LLC isn't formally registered yet, **register it before submitting**
— Meta rejects unverified businesses for `instagram_content_publish`.

### Deauthorization callback (TODO before submission)

Meta requires a deauthorization callback URL. We don't ship one yet. Two
choices:
1. **Quick path**: list `https://app.summitautomates.com/data-deletion` as
   the callback. Meta accepts a manual deletion process. Our Data Deletion
   page already documents this.
2. **Proper path (do this in Phase 5 dev work)**: implement
   `POST /api/oauth/meta/deauthorize` that receives Meta's signed request
   when a user removes Summit from their FB Settings → Business
   Integrations. The handler decodes the signed request, finds the
   matching SocialAccount, and deletes it. ~2 hours of work; nice to have
   before submission.

---

## B. Google OAuth Verification (YouTube)

**Where**: Google Cloud Console → Your Project → APIs & Services → OAuth consent screen → Submit for verification

**Project configuration**:

| Field | Value |
|---|---|
| Application name | Summit Automates |
| User support email | admin@summitautomates.com |
| Developer contact email | admin@summitautomates.com |
| Application home page | https://summitautomates.com |
| Privacy policy URL | https://app.summitautomates.com/privacy |
| Terms of service URL | https://app.summitautomates.com/terms |
| Authorized domain | summitautomates.com (covers app. + api. subdomains) |
| Authorized redirect URI | https://api.summitautomates.com/api/oauth/youtube/callback |
| Application type | Web application |

### Scopes to request

- `https://www.googleapis.com/auth/youtube.upload` — **sensitive scope, requires verification**
- `https://www.googleapis.com/auth/youtube.readonly` — sensitive

Both are sensitive. You'll need verification.

### Scope justification

Paste in the "Scope justification" field:
> Summit Automates uploads videos to the user's own YouTube channel on
> their behalf. The user connects their channel via OAuth and configures
> a publishing schedule in our admin panel. Each video has been
> generated by our AI pipeline using the user's brought-your-own-key AI
> providers (OpenAI, ElevenLabs, etc.) and reviewed by the user before
> publication. We use `youtube.upload` to call `videos.insert`. We use
> `youtube.readonly` only to fetch the channel title and ID for display
> in the user's "Connected accounts" view. We do not read or modify any
> existing videos, comments, playlists, or subscriber data.

### Demo video (required for sensitive scope verification)

Record a screencast (1–3 min):
1. Sign into Summit Automates
2. Connect YouTube via OAuth
3. Generate a post (or use a pre-generated one)
4. Click "Post Now" → YouTube
5. Switch to YouTube Studio and show the uploaded video

### Domain verification

Verify domain ownership in Google Search Console using DNS TXT record or
HTML file. Required before submission.

---

## C. TikTok Content Posting API audit

**Where**: developers.tiktok.com → Your App → Add Products → Content Posting API → Submit for audit

**App configuration**:

| Field | Value |
|---|---|
| App name | Summit Automates |
| App icon | (upload your logo — 1024×1024 PNG) |
| Description | AI-powered content generation and posting for niche social media operators. |
| Category | Productivity |
| Website | https://summitautomates.com |
| Terms of service URL | https://app.summitautomates.com/terms |
| Privacy policy URL | https://app.summitautomates.com/privacy |
| Redirect URI | https://api.summitautomates.com/api/oauth/tiktok/callback |
| Webhook URL (events) | Leave blank unless you need post-status webhooks |

### Scopes to request

- `user.info.basic` — read basic profile (display name, open ID) so we can show the connected account
- `video.upload` — upload video files
- `video.publish` — publish videos as user-facing posts (**this is the sensitive one**)

### Use-case explanation

Paste in the "Describe your app" field:
> Summit Automates is a SaaS tool that lets creators automate the
> distribution of short-form video content they have created with our
> AI pipeline. After the creator connects their TikTok account via
> OAuth, our pipeline generates vertical 9:16 videos based on a content
> niche the creator configures. The creator reviews the generated video
> + caption in our admin panel and either publishes immediately or
> schedules for a future time. Every TikTok post originates from a user
> action in our admin panel; no posting happens without the user's
> explicit instruction. We support TikTok's `direct_post` mode for users
> who want to publish immediately and `upload_only` mode for users who
> want to add the video to drafts and edit on TikTok before posting.

### Demo video

Record (2–3 min):
1. Sign into Summit Automates
2. Connect TikTok account
3. Generate a vertical short video
4. Post-now to TikTok with `video.publish` scope
5. Switch to TikTok mobile app and show the new post

### Privacy + content guidelines

TikTok audits for spammy / inauthentic behavior. Your app description and
demo should emphasize:
- **User-initiated**: the user clicks "Post Now" — not autonomous
- **Niche-specific content**: not generic spam
- **Original creation**: the AI generates new videos (not reposts)
- **Rate-limited**: respect TikTok's posting limits (5/day per user)

### Watermark requirement

TikTok requires a watermark on AI-generated video uploaded through
Content Posting API. Phase 5 dev TODO: add a small "AI-generated"
watermark to videos that will go to TikTok. Mention this in your
submission: "Generated videos include an AI watermark in compliance
with TikTok's AIGC labeling requirements."

---

## D. LinkedIn — Share on LinkedIn product

**Where**: developer.linkedin.com → Your App → Products → Request access to "Share on LinkedIn"

**App configuration**:

| Field | Value |
|---|---|
| App name | Summit Automates |
| LinkedIn Page (required) | You must create a LinkedIn Page for "Summit Automates" first |
| Logo | 1024×1024 PNG |
| Description | AI content automation for professional creators on LinkedIn. |
| Website | https://summitautomates.com |
| Business email | admin@summitautomates.com |
| Privacy policy URL | https://app.summitautomates.com/privacy |
| Legal agreement URL | https://app.summitautomates.com/terms |
| Authorized redirect URL | https://api.summitautomates.com/api/oauth/linkedin/callback |

### Scopes to request

- `openid`, `profile`, `email` — standard OIDC for sign-in
- `w_member_social` — **the sensitive one** — publish posts on behalf of the connected member

### Use-case justification

Paste in the product request form:
> Summit Automates publishes long-form 16:9 videos (3–5 minutes) to the
> connected LinkedIn member's feed. These videos are generated by our
> AI pipeline based on a content niche the user has configured (e.g.
> "weekly market commentary for B2B SaaS founders"). The user reviews
> every generated video and approves it in our admin panel before it
> publishes. We use `w_member_social` to call the LinkedIn Posts API
> (`/rest/posts`) with the video asset URN returned by the Videos API
> upload flow. We do not read the user's feed, connections, or messages.

### Logo + page requirement

LinkedIn requires you to have a **LinkedIn Page** for Summit Automates
*before* you can request access to `w_member_social`. Create one at
linkedin.com/company/setup/new.

---

## Submission order recommendation

Submit in this order. Each is gated only on legal URLs being live + the
prerequisites above; you can fire all four off in one afternoon.

1. **LinkedIn first** — fastest review (3–7 days), gives you a quick win
2. **Google second** — medium difficulty, you'll need to verify the domain in Search Console anyway
3. **Meta third** — start business verification now since it has its own ~1 week lead time
4. **TikTok last** — needs the AI watermark in code; submit after that ships

---

## Tracking sheet

Copy this into a Google Sheet to track each submission:

| Platform | Submitted on | Review URL | Status | Notes |
|---|---|---|---|---|
| LinkedIn | | | | |
| Google | | | | |
| Meta | | | | |
| TikTok | | | | |

---

## Materials checklist before any submission

- [x] LLC registered — Summit Systems (Private) Limited, UIN 0324466
- [x] DNS live — app. + api. subdomains resolve, Let's Encrypt certs valid
- [x] `/terms`, `/privacy`, `/data-deletion` reachable (200) on app.summitautomates.com
- [x] Legal entity placeholders filled in (terms.tsx / privacy.tsx)
- [x] Self-serve signup live at app.summitautomates.com/signup
- [ ] Reviewer test login `reviewer@summitautomates.com` created with realistic test data (a niche, sample posts, sample connected accounts)
- [ ] **Per-platform: create the developer app + obtain client ID/secret**, then set the real env vars on Railway (currently placeholders)
- [ ] Demo social accounts created on each platform (`summit_demo` handle)
- [ ] Logo / app icon: 1024×1024 PNG
- [ ] Screencast video uploaded to YouTube unlisted (so each platform can review it)

---

## What's blocking each submission RIGHT NOW

The kit answers are ready, but each platform needs a developer app created
first (which gives you the client ID/secret to paste into Railway env vars).
Here's the critical path per platform:

| Platform | You must first… | Then I can… |
|---|---|---|
| **Meta** | 1. Create app at developers.facebook.com 2. Start Business Verification (upload SECP cert — `INCORPORATION CERTIFICATE (SUMMIT SYSTEMS).pdf`) | Wire `META_APP_ID`/`META_APP_SECRET`, register the callback URL, fill the review form from this kit |
| **Google** | 1. Create project at console.cloud.google.com 2. Verify domain in Search Console | Wire `GOOGLE_CLIENT_ID`/`SECRET`, configure consent screen, request the YouTube scopes |
| **TikTok** | 1. Register at developers.tiktok.com 2. (code) add AI watermark to videos | Wire `TIKTOK_CLIENT_KEY`/`SECRET`, submit Content Posting API audit |
| **LinkedIn** | 1. Create a LinkedIn **Company Page** for Summit Automates 2. Create app at developer.linkedin.com linked to that Page | Wire `LINKEDIN_CLIENT_ID`/`SECRET`, request "Share on LinkedIn" |

The env var placeholders are already on Railway (`placeholder` values) — once
you create each developer app, send me the client ID + secret and I'll swap
them in and register the callback URLs.
