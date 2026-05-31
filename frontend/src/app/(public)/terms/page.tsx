import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service — Summit Automates",
  description: "The rules of using Summit Automates.",
};

const LAST_UPDATED = "2026-05-19";

export default function TermsPage() {
  return (
    <article className="mx-auto max-w-3xl px-6 py-16 prose prose-slate prose-headings:font-semibold">
      <p className="text-sm text-slate-500">Last updated: {LAST_UPDATED}</p>
      <h1>Terms of Service</h1>

      <p>
        These Terms of Service (&quot;Terms&quot;) govern your use of{" "}
        <strong>Summit Automates</strong> (&quot;the Service&quot;), a product
        operated by <strong>Summit Systems (Private) Limited</strong>, a
        private limited company incorporated in Pakistan under Corporate
        Unique Identification Number 0324466 (&quot;Summit&quot;,
        &quot;we&quot;, or &quot;us&quot;), with registered office at{" "}
        <em>
          Office&nbsp;# 3, First Floor, Mughal Market, Al-Rehman Arcade,
          Sector G-13/2, Islamabad, Pakistan
        </em>
        , available at{" "}
        <a href="https://summitautomates.com">summitautomates.com</a> and{" "}
        <a href="https://app.summitautomates.com">app.summitautomates.com</a>
        . By accessing or using the Service, you agree to these Terms.
      </p>

      <h2>1. What the Service does</h2>
      <p>
        Summit Automates is a software tool that, using API keys you provide,
        generates social-media video content and publishes that content to
        social media accounts you have connected via OAuth. Specifically, the
        Service:
      </p>
      <ul>
        <li>Discovers topics relevant to a niche you define</li>
        <li>
          Generates a script, scene images, voiceover, music, and a final
          video using third-party AI providers
        </li>
        <li>
          Posts the generated content to social media accounts (Instagram,
          Facebook, YouTube, TikTok, LinkedIn) you have connected
        </li>
        <li>
          Tracks every API call&apos;s cost so you can monitor what the
          underlying AI providers charge you
        </li>
      </ul>

      <h2>2. Eligibility</h2>
      <p>
        You must be at least 18 years old (or the age of majority in your
        jurisdiction) and able to enter into a binding contract. By using the
        Service you represent that you meet these requirements and that the
        information you provide is accurate.
      </p>

      <h2>3. Your account</h2>
      <p>You are responsible for:</p>
      <ul>
        <li>Keeping your login credentials confidential</li>
        <li>
          The accuracy of the API keys you provide and any charges incurred by
          your AI providers as a result of your use of the Service
        </li>
        <li>
          All content generated, scheduled, or published from your workspace
        </li>
        <li>
          Complying with the terms of service of each social platform you
          connect (Meta, Google/YouTube, TikTok, LinkedIn) — your account on
          those platforms can be suspended for spam, misleading content, or
          policy violations even if the violation was caused by content
          Summit generated
        </li>
      </ul>

      <h2>4. Bring your own keys (BYOK)</h2>
      <p>
        Summit is a BYOK service. You supply API keys for the AI providers you
        choose (OpenAI, ElevenLabs, Pexels, Google Gemini, Anthropic, etc.).
        You are billed directly by those providers; Summit does not mark up or
        re-bill API usage. We are not responsible for outages, price changes,
        rate limits, or content moderation decisions made by your AI
        providers.
      </p>

      <h2>5. Acceptable use</h2>
      <p>You agree not to use the Service to:</p>
      <ul>
        <li>
          Generate or publish content that is illegal, defamatory, hateful,
          sexually explicit, or incites violence
        </li>
        <li>
          Impersonate individuals, brands, or businesses you do not represent
        </li>
        <li>
          Conduct spam, mass-following / unfollowing, or other behaviors that
          violate any connected platform&apos;s acceptable-use policies
        </li>
        <li>Reverse-engineer or extract source code from the Service</li>
        <li>
          Resell, sublicense, or rent the Service to third parties without our
          written permission
        </li>
        <li>
          Bypass rate limits, security measures, or features intended to
          enforce these Terms
        </li>
      </ul>
      <p>
        We may suspend or terminate your account at our reasonable discretion
        if we believe you have violated these rules.
      </p>

      <h2>6. Subscriptions and billing</h2>
      <p>
        Subscriptions are processed by <strong>Whop Inc.</strong> as merchant
        of record. By subscribing you agree to Whop&apos;s terms in addition
        to ours. Subscription fees are billed in advance; renewals are
        automatic until you cancel.
      </p>
      <p>
        <strong>Trial.</strong> If we offer a free trial, charges begin at the
        end of the trial unless you cancel before then. You will receive a
        reminder email before the trial ends.
      </p>
      <p>
        <strong>Cancellation.</strong> You may cancel at any time from your
        Whop dashboard. Cancellation takes effect at the end of your current
        billing period. We do not pro-rate refunds for partial periods unless
        required by law.
      </p>
      <p>
        <strong>Refunds.</strong> Refunds are at our reasonable discretion and
        are processed through Whop.
      </p>

      <h2>7. Intellectual property</h2>
      <p>
        <strong>Your content.</strong> You retain all rights to the content
        you provide (your niche descriptions, prompts, etc.) and to the
        content the Service generates on your behalf. We claim no ownership in
        your generated videos, captions, or hashtags. Note however that AI
        provider outputs may be subject to the provider&apos;s own terms (for
        example, some providers do not grant exclusive rights to outputs).
      </p>
      <p>
        <strong>Our software.</strong> The Service software, design, and
        documentation are owned by Summit and protected by applicable
        intellectual-property laws. These Terms grant you a non-exclusive,
        non-transferable license to use the Service for the duration of your
        subscription.
      </p>

      <h2>8. Disclaimers</h2>
      <p>
        The Service is provided <strong>&quot;as is&quot; and &quot;as available&quot;</strong>{" "}
        without warranties of any kind, express or implied, including but not
        limited to merchantability, fitness for a particular purpose, and
        non-infringement. We do not warrant that the Service will be
        uninterrupted, error-free, or that any generated content will be
        suitable, accurate, or compliant with any specific platform&apos;s
        policies.
      </p>
      <p>
        Specifically: we do not guarantee any particular outcome (engagement,
        followers, revenue) from posts published via the Service.
      </p>

      <h2>9. Limitation of liability</h2>
      <p>
        To the maximum extent permitted by law, in no event will Summit, its
        affiliates, officers, employees, or contractors be liable for any
        indirect, incidental, special, consequential, or punitive damages
        arising out of or related to your use of the Service. Our total
        aggregate liability for any claim arising under these Terms is
        limited to the greater of (a) the fees you paid us in the three
        months preceding the event giving rise to the claim, or (b)
        US$100.
      </p>
      <p>
        This limitation applies even if we have been advised of the
        possibility of such damages.
      </p>

      <h2>10. Indemnification</h2>
      <p>
        You agree to indemnify and hold Summit harmless from any claims,
        damages, liabilities, and expenses (including reasonable legal fees)
        arising from (a) your content, (b) your use of the Service, (c) your
        violation of these Terms, or (d) your violation of any third party&apos;s
        rights, including any social platform&apos;s terms of service.
      </p>

      <h2>11. Termination</h2>
      <p>
        Either party may terminate your account at any time. On termination
        your access to the Service ceases immediately, and we will delete your
        workspace data within 30 days unless you request immediate deletion.
        See the <a href="/data-deletion">Data Deletion Instructions</a> for
        details.
      </p>

      <h2>12. Governing law and dispute resolution</h2>
      <p>
        These Terms are governed by and construed in accordance with the laws
        of the <strong>Islamic Republic of Pakistan</strong>, without regard
        to its conflict-of-law principles. You agree that the courts of{" "}
        <em>Islamabad</em>, Pakistan, will have exclusive jurisdiction over
        any dispute arising out of or relating to these Terms.
      </p>

      <h2>13. Changes to these Terms</h2>
      <p>
        We may update these Terms from time to time. Material changes will be
        communicated to you by email and posted on this page with a revised
        &quot;Last updated&quot; date. Continued use of the Service after a
        change takes effect constitutes your acceptance of the revised Terms.
      </p>

      <h2>14. Contact</h2>
      <p>
        Questions?{" "}
        <a href="mailto:admin@summitautomates.com">
          admin@summitautomates.com
        </a>
        .
      </p>
    </article>
  );
}
