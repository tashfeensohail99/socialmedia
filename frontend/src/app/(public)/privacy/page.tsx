import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — Summit Automates",
  description: "How Summit Automates collects, stores, and processes data.",
};

const LAST_UPDATED = "2026-05-19";

export default function PrivacyPage() {
  return (
    <article className="mx-auto max-w-3xl px-6 py-16 prose prose-slate prose-headings:font-semibold">
      <p className="text-sm text-slate-500">Last updated: {LAST_UPDATED}</p>
      <h1>Privacy Policy</h1>

      <p>
        This Privacy Policy describes how <strong>Summit Automates</strong>{" "}
        (&quot;we&quot;, &quot;us&quot;, or &quot;Summit&quot;), a product
        operated by <strong>Summit Systems (Private) Limited</strong>, a
        private limited company incorporated in Pakistan (Corporate Unique
        Identification Number 0324466) with registered office at{" "}
        <em>
          Office&nbsp;# 3, First Floor, Mughal Market, Al-Rehman Arcade,
          Sector G-13/2, Islamabad, Pakistan
        </em>
        , collects, stores, processes, and discloses information when you
        use the service available at{" "}
        <a href="https://summitautomates.com">summitautomates.com</a> and{" "}
        <a href="https://app.summitautomates.com">app.summitautomates.com</a>{" "}
        (the &quot;Service&quot;).
      </p>

      <h2>1. Information we collect</h2>

      <h3>1.1 Account information</h3>
      <p>When you sign up, we collect:</p>
      <ul>
        <li>Your email address</li>
        <li>An encrypted password hash (we never store the plaintext)</li>
        <li>A workspace name and any other configuration you provide</li>
      </ul>

      <h3>1.2 Bring-your-own AI provider keys</h3>
      <p>
        Summit Automates is a bring-your-own-key (BYOK) service. You provide
        API keys for the AI providers you choose to use (OpenAI, ElevenLabs,
        Pexels, Google Gemini, etc.). These keys are{" "}
        <strong>
          encrypted at rest using AES-128-CBC + HMAC-SHA256 (via the Fernet
          token scheme)
        </strong>{" "}
        and are only decrypted at the moment a job runs. We never display, log,
        or transmit your plaintext keys to anyone — including ourselves.
      </p>

      <h3>1.3 Social platform OAuth tokens</h3>
      <p>
        When you connect a social platform (Instagram, Facebook, YouTube,
        TikTok, LinkedIn), we receive OAuth access and refresh tokens scoped to
        the permissions you grant on that platform&apos;s consent screen. We
        store these tokens encrypted using the same Fernet scheme as above. We
        do not request or receive your social account passwords at any point.
      </p>

      <h3>1.4 Content data from connected platforms</h3>
      <p>
        For each social account you connect, we may read the following data{" "}
        <em>only</em> in service of the features you have explicitly enabled:
      </p>
      <ul>
        <li>
          <strong>Account metadata</strong>: account handle, account ID,
          channel title, page name. Used to display the connection in your
          admin panel.
        </li>
        <li>
          <strong>Connected Instagram Business / Creator account information</strong>:
          for Meta connections, we read the Instagram account&apos;s
          Business/Creator details so we can publish posts on your behalf
          via the Instagram Graph API.
        </li>
      </ul>
      <p>
        <strong>We do not collect or store:</strong> private messages,
        direct messages, contacts/followers lists for marketing, audience
        analytics, or any post engagement data beyond what is necessary to
        confirm a publish succeeded.
      </p>

      <h3>1.5 Content you generate</h3>
      <p>
        Generated content (videos, captions, hashtags, narrative scripts,
        thumbnail images) is stored in your workspace and on your media
        storage. We retain these so you can review, edit, or republish.
      </p>

      <h3>1.6 Usage data</h3>
      <p>
        Every external API call made on your behalf is logged as a usage event
        containing the provider name, model identifier, token / unit counts,
        and computed cost in USD. We use this to power the cost dashboard
        inside your workspace. We do not share this data with any third party.
      </p>

      <h3>1.7 Payment information</h3>
      <p>
        Payments are processed by <strong>Whop Inc.</strong> (
        <a href="https://whop.com" target="_blank" rel="noreferrer">
          whop.com
        </a>
        ) acting as the merchant of record. Summit Automates does{" "}
        <strong>not</strong> receive, store, or have access to your credit
        card or bank account information. We receive only:
      </p>
      <ul>
        <li>A Whop membership ID linking your subscription</li>
        <li>Your billing email (used to authenticate you into Summit)</li>
        <li>Subscription lifecycle events (created, renewed, cancelled, refunded)</li>
      </ul>
      <p>
        Whop&apos;s own privacy policy applies to payment data. See{" "}
        <a href="https://whop.com/legal/privacy" target="_blank" rel="noreferrer">
          whop.com/legal/privacy
        </a>
        .
      </p>

      <h3>1.8 Logs</h3>
      <p>
        We log server-side errors, request paths, and HTTP status codes for the
        purpose of operating and debugging the Service. Request logs do not
        include the contents of your generated posts or your API keys.
      </p>

      <h2>2. How we use your data</h2>
      <p>We process the data described above solely to:</p>
      <ul>
        <li>Run the content-generation pipeline you have configured</li>
        <li>Publish posts to the social platforms you have connected, on your behalf</li>
        <li>Show you the status, cost, and history of those operations</li>
        <li>Bill you via Whop and surface your subscription state in the Service</li>
        <li>Send transactional emails (magic-link login, trial expiration, post failure notices)</li>
        <li>Diagnose and fix bugs</li>
      </ul>
      <p>
        We do <strong>not</strong> use your data for:
      </p>
      <ul>
        <li>Advertising or behavioral profiling</li>
        <li>Training any machine learning model</li>
        <li>Selling or renting to data brokers</li>
        <li>Any purpose other than operating the Service for you</li>
      </ul>

      <h2>3. Sub-processors</h2>
      <p>
        We use the following sub-processors to operate the Service. Where you
        bring your own keys, your traffic goes directly to the provider; in
        other cases data passes through us first.
      </p>
      <ul>
        <li>
          <strong>Whop Inc.</strong> — payment processing and subscription
          management
        </li>
        <li>
          <strong>Railway</strong> (railway.com) — application hosting,
          PostgreSQL database, media storage
        </li>
        <li>
          <strong>Resend</strong> (resend.com) — transactional email delivery
        </li>
        <li>
          <strong>AI providers you choose</strong> — OpenAI, Anthropic, Google
          (Gemini), ElevenLabs, Pexels, Unsplash. Calls are made with the keys
          you provide; data sent is subject to each provider&apos;s privacy
          policy.
        </li>
        <li>
          <strong>Social platforms you connect</strong> — Meta (Instagram +
          Facebook), Google (YouTube), TikTok, LinkedIn. Data sent is subject
          to each platform&apos;s policy.
        </li>
      </ul>

      <h2>4. Data retention</h2>
      <p>
        We retain your workspace data for as long as your account is active. If
        you cancel your subscription, we retain your workspace data for{" "}
        <strong>30 days</strong> so you can resubscribe without data loss.
        After 30 days, all workspace data — including encrypted API keys,
        OAuth tokens, generated posts, and usage events — is permanently
        deleted.
      </p>
      <p>
        You may request immediate deletion at any time. See the{" "}
        <a href="/data-deletion">Data Deletion Instructions</a>.
      </p>

      <h2>5. Your rights</h2>
      <p>You have the right to:</p>
      <ul>
        <li>
          <strong>Access</strong> all data we hold about you (available from
          your admin panel and on request)
        </li>
        <li>
          <strong>Correct</strong> any inaccurate information about you
        </li>
        <li>
          <strong>Delete</strong> your data (see{" "}
          <a href="/data-deletion">Data Deletion Instructions</a>)
        </li>
        <li>
          <strong>Export</strong> a machine-readable copy of your workspace
          data on request
        </li>
        <li>
          <strong>Revoke</strong> social platform access at any time by
          disconnecting the account in the admin panel or by revoking the
          permission on the platform itself
        </li>
      </ul>

      <h2>6. Security</h2>
      <p>
        We follow industry-standard practices, including TLS for all data in
        transit, Fernet (authenticated AES) encryption for sensitive data at
        rest, bcrypt password hashing, JWT-based authentication, and
        least-privilege access controls on our infrastructure. No system is
        impenetrable; we will notify affected users without undue delay if we
        learn of a security incident impacting your data.
      </p>

      <h2>7. Children</h2>
      <p>
        The Service is not directed to children under 13 (or 16 in the EU/UK).
        We do not knowingly collect personal information from children. If we
        learn we have, we will delete it.
      </p>

      <h2>8. International transfers</h2>
      <p>
        We operate from Pakistan and use sub-processors located in the United
        States and Europe. By using the Service you consent to your data being
        transferred to and processed in those jurisdictions.
      </p>

      <h2>9. Changes to this policy</h2>
      <p>
        We may update this policy from time to time. Material changes will be
        announced via email to your registered address. Continued use of the
        Service after a change takes effect constitutes acceptance.
      </p>

      <h2>10. Contact us</h2>
      <p>
        Questions about this policy or about your data?{" "}
        <a href="mailto:admin@summitautomates.com">
          admin@summitautomates.com
        </a>
        .
      </p>
    </article>
  );
}
