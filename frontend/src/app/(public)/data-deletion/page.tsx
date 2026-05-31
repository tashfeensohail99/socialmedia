import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Deletion — Summit Automates",
  description:
    "How to request deletion of your Summit Automates workspace and any data we hold from connected social platforms.",
};

const LAST_UPDATED = "2026-05-19";

export default function DataDeletionPage() {
  return (
    <article className="mx-auto max-w-3xl px-6 py-16 prose prose-slate prose-headings:font-semibold">
      <p className="text-sm text-slate-500">Last updated: {LAST_UPDATED}</p>
      <h1>Data Deletion Instructions</h1>

      <p>
        This page tells you how to delete data Summit Automates holds about you
        or about social media accounts you have connected via OAuth. We
        provide both <strong>self-service</strong> and <strong>email-based</strong>{" "}
        deletion paths. Meta, Google, TikTok, and LinkedIn all require us to
        provide this information publicly — this is that page.
      </p>

      <h2>Option A — Self-service deletion (recommended)</h2>
      <p>If you have access to your Summit Automates workspace:</p>
      <ol>
        <li>
          <strong>Sign in</strong> to your workspace at{" "}
          <a href="https://summitautomates.com/login">
            summitautomates.com/login
          </a>
          .
        </li>
        <li>
          <strong>Disconnect each social account</strong> from{" "}
          <em>Social Accounts</em> in the sidebar. This immediately deletes
          our stored OAuth tokens for those accounts. We also recommend
          revoking the app on each platform itself (links below).
        </li>
        <li>
          <strong>Delete your API keys</strong> from <em>API Keys</em>. We
          permanently remove the encrypted blobs from our database.
        </li>
        <li>
          <strong>Delete generated posts</strong> from <em>Posts</em> if you
          want media files removed from our storage too. Each post&apos;s
          videos, images, voiceover, and music are deleted with it.
        </li>
        <li>
          <strong>Cancel your subscription</strong> in your Whop dashboard.
          Your workspace will be automatically purged 30 days after
          cancellation.
        </li>
      </ol>

      <h2>Option B — Immediate full deletion by email</h2>
      <p>
        To request <strong>immediate</strong> deletion of your entire
        workspace and all associated data — including encrypted API keys,
        encrypted OAuth tokens, generated content, usage events, and any
        backups:
      </p>
      <ol>
        <li>
          Email{" "}
          <a href="mailto:admin@summitautomates.com?subject=Data%20deletion%20request">
            admin@summitautomates.com
          </a>{" "}
          from the email address tied to your account.
        </li>
        <li>
          Subject line: <code>Data deletion request</code>
        </li>
        <li>
          Include in the body: a confirmation that you want all data deleted
          and any specific scope (e.g. &quot;delete only my Instagram
          connection and its tokens&quot; vs &quot;delete my entire workspace&quot;).
        </li>
      </ol>
      <p>
        We respond within <strong>3 business days</strong> with confirmation
        and complete the deletion within <strong>30 days</strong> of receipt
        (typically much sooner — usually the same day for workspace data;
        any backup copies are purged on our scheduled rotation within 30
        days).
      </p>

      <h2>Option C — Revoke the app on the platform itself</h2>
      <p>
        You can revoke Summit Automates&apos; access to a connected social
        account directly on the platform. This invalidates the tokens we
        hold, even before we delete them, so we can no longer act on your
        behalf:
      </p>
      <ul>
        <li>
          <strong>Instagram &amp; Facebook</strong>:{" "}
          <a
            href="https://www.facebook.com/settings?tab=business_tools"
            target="_blank"
            rel="noreferrer"
          >
            facebook.com/settings → Business Integrations → Summit Automates → Remove
          </a>
        </li>
        <li>
          <strong>YouTube (Google)</strong>:{" "}
          <a
            href="https://myaccount.google.com/permissions"
            target="_blank"
            rel="noreferrer"
          >
            myaccount.google.com/permissions → Summit Automates → Remove access
          </a>
        </li>
        <li>
          <strong>TikTok</strong>:{" "}
          <a
            href="https://www.tiktok.com/setting/connected-apps"
            target="_blank"
            rel="noreferrer"
          >
            tiktok.com/setting/connected-apps → Summit Automates → Disconnect
          </a>
        </li>
        <li>
          <strong>LinkedIn</strong>:{" "}
          <a
            href="https://www.linkedin.com/psettings/permitted-services"
            target="_blank"
            rel="noreferrer"
          >
            linkedin.com/psettings/permitted-services → Summit Automates → Remove
          </a>
        </li>
      </ul>
      <p>
        Revoking on the platform stops further activity but does not delete
        the data we already hold. Use Option A or B in addition for full
        deletion.
      </p>

      <h2>What gets deleted</h2>
      <p>A full workspace deletion removes:</p>
      <ul>
        <li>Your user account and password hash</li>
        <li>Your tenant&apos;s niche configurations and prompt overrides</li>
        <li>All stored API keys (encrypted blobs)</li>
        <li>All stored OAuth tokens (encrypted blobs)</li>
        <li>All discovered topics and their scores</li>
        <li>
          All generated posts, including video files, images, voiceover audio,
          music, and thumbnails (from our application database and from media
          storage)
        </li>
        <li>All scheduled posts and posting attempts</li>
        <li>All usage events / cost tracking history</li>
        <li>Posting rules and prompt templates</li>
      </ul>
      <p>
        Server-side request logs (containing only HTTP paths, status codes,
        and error stack traces — never your content) may be retained for up
        to <strong>30 days</strong> for security and debugging purposes,
        after which they are deleted automatically.
      </p>

      <h2>Confirmation</h2>
      <p>
        After deletion completes, you will receive an email at the address
        associated with your account confirming the action and listing what
        was removed. If you don&apos;t receive this confirmation, contact us
        again at{" "}
        <a href="mailto:admin@summitautomates.com">admin@summitautomates.com</a>
        .
      </p>

      <h2>For Meta App Review reviewers</h2>
      <p>
        The deletion endpoint for compliance with Meta&apos;s Platform Terms is
        the email address{" "}
        <a href="mailto:admin@summitautomates.com">admin@summitautomates.com</a>{" "}
        plus the self-service flow described in Option A above. We respond to
        all deletion requests within the timeframe required by Meta&apos;s
        Platform Terms (currently 30 days). A user-initiated revoke on
        Facebook (Option C above) also triggers our automatic deletion of
        their OAuth tokens via Meta&apos;s deauthorization callback once we
        ship that endpoint in a future release; until then, the manual paths
        in Options A and B apply.
      </p>
    </article>
  );
}
