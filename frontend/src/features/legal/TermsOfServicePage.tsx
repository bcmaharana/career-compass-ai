import { LegalPageLayout, LegalSection } from "@/features/legal/LegalPageLayout";

export function TermsOfServicePage() {
  return (
    <LegalPageLayout
      title="Terms of Service"
      effectiveDate="August 11, 2026"
      summary={
        <>
          <p>
            You must be 18+ to use Career Compass AI. Don't misuse the service, don't share your
            account, and treat AI-generated suggestions as a starting point, not professional
            advice — always verify them yourself. You can delete your account and all your data at
            any time. We provide the service "as is," without warranties, and our liability is
            limited as described below.
          </p>
        </>
      }
    >
      <LegalSection title="1. Acceptance of these Terms">
        <p>
          These Terms of Service ("Terms") are a legal agreement between you and Career Compass AI
          ("we," "us," "our") governing your access to and use of the Career Compass AI website,
          application, and related services (together, the "Service"). By creating an account or
          otherwise using the Service, you agree to be bound by these Terms and by our{" "}
          <a href="/privacy" className="underline">
            Privacy Policy
          </a>
          , which is incorporated into these Terms by reference. If you do not agree, do not use
          the Service.
        </p>
      </LegalSection>

      <LegalSection title="2. Eligibility">
        <p>
          You must be at least 18 years old to create an account or use the Service. By using the
          Service, you represent that you meet this requirement and that you have the legal
          capacity to enter into these Terms. If you are using the Service on behalf of an
          organization, you represent that you have the authority to bind that organization to
          these Terms.
        </p>
      </LegalSection>

      <LegalSection title="3. Your account">
        <p>
          You are responsible for maintaining the confidentiality of your login credentials and
          for all activity that occurs under your account. Notify us promptly at{" "}
          <a href="mailto:bcmaharana@hotmail.com" className="underline">
            bcmaharana@hotmail.com
          </a>{" "}
          if you believe your account has been compromised. You agree to provide accurate
          information when creating and maintaining your account.
        </p>
      </LegalSection>

      <LegalSection title="4. Acceptable use">
        <p>You agree not to:</p>
        <ul className="ml-5 list-disc space-y-1">
          <li>Use the Service for any unlawful purpose or in violation of any applicable law;</li>
          <li>
            Upload content you don't have the right to share, or that infringes someone else's
            intellectual property or privacy rights;
          </li>
          <li>
            Attempt to gain unauthorized access to another user's account or to any part of the
            Service's infrastructure;
          </li>
          <li>
            Use automated means (scraping, bots, etc.) to access the Service outside of any
            official API we may offer;
          </li>
          <li>
            Interfere with or disrupt the integrity or performance of the Service, including its
            AI features;
          </li>
          <li>Impersonate any person or entity, or misrepresent your affiliation with one.</li>
        </ul>
      </LegalSection>

      <LegalSection title="5. AI features">
        <p>
          The Service uses artificial intelligence — including third-party AI providers — to
          generate career recommendations, skill-gap analyses, resume extraction, and chat
          responses ("AI Outputs"). AI Outputs are generated automatically and{" "}
          <strong>may be inaccurate, incomplete, or unsuitable for your specific situation</strong>
          . AI Outputs are provided for informational purposes only and do not constitute
          professional career, legal, financial, or employment advice. You are solely responsible
          for evaluating and independently verifying any AI Output before relying on it, including
          before making any employment, financial, or career decision.
        </p>
      </LegalSection>

      <LegalSection title="6. Your content">
        <p>
          You retain ownership of the career profile information, resumes, and other content you
          submit to the Service ("Your Content"). By submitting Your Content, you grant us a
          limited license to store, process, and transmit it — including to third-party AI
          providers where applicable — solely as necessary to operate and provide the Service to
          you, as described in our{" "}
          <a href="/privacy" className="underline">
            Privacy Policy
          </a>
          . We do not claim ownership of Your Content and do not sell it.
        </p>
      </LegalSection>

      <LegalSection title="7. Intellectual property">
        <p>
          The Service itself — its software, design, and branding, excluding Your Content — is
          owned by Career Compass AI and protected by applicable intellectual property laws. These
          Terms do not grant you any right to use our branding or trademarks without our prior
          written consent.
        </p>
      </LegalSection>

      <LegalSection title="8. Termination and account deletion">
        <p>
          You may permanently delete your account at any time from Settings. Deletion is immediate
          and irreversible — it removes your account, career profile, resumes, and chat history
          from our systems, with no recovery period. We may suspend or terminate your access to
          the Service if we reasonably believe you have violated these Terms, though we will make
          reasonable efforts to notify you first except where immediate action is warranted (e.g.
          to prevent harm or abuse).
        </p>
      </LegalSection>

      <LegalSection title="9. Disclaimer of warranties">
        <p>
          THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE," WITHOUT WARRANTIES OF ANY KIND,
          WHETHER EXPRESS, IMPLIED, OR STATUTORY, INCLUDING WITHOUT LIMITATION WARRANTIES OF
          MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT. WE DO NOT
          WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE, OR THAT AI OUTPUTS
          WILL BE ACCURATE OR RELIABLE.
        </p>
      </LegalSection>

      <LegalSection title="10. Limitation of liability">
        <p>
          TO THE MAXIMUM EXTENT PERMITTED BY LAW, CAREER COMPASS AI WILL NOT BE LIABLE FOR ANY
          INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF
          PROFITS, DATA, OR GOODWILL, ARISING FROM OR RELATED TO YOUR USE OF THE SERVICE, EVEN IF
          WE HAVE BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. OUR TOTAL LIABILITY FOR ANY
          CLAIM ARISING FROM THESE TERMS OR THE SERVICE WILL NOT EXCEED THE GREATER OF (A) THE
          AMOUNT YOU PAID US IN THE 12 MONTHS BEFORE THE CLAIM AROSE, OR (B) FIFTY U.S. DOLLARS
          ($50). SOME JURISDICTIONS DO NOT ALLOW THE EXCLUSION OR LIMITATION OF CERTAIN DAMAGES, SO
          SOME OF THE ABOVE LIMITATIONS MAY NOT APPLY TO YOU.
        </p>
      </LegalSection>

      <LegalSection title="11. Changes to these Terms">
        <p>
          We may update these Terms from time to time. If we make material changes, we will notify
          you by email or through an in-app notice before the changes take effect. Continued use of
          the Service after changes take effect constitutes acceptance of the updated Terms.
        </p>
      </LegalSection>

      <LegalSection title="12. Governing law">
        <p>
          These Terms are governed by the laws of the Commonwealth of Pennsylvania, United States,
          without regard to its conflict-of-laws principles. Any dispute arising from these Terms
          or the Service will be subject to the exclusive jurisdiction of the state and federal
          courts located in Pennsylvania.
        </p>
      </LegalSection>

      <LegalSection title="13. Contact">
        <p>
          Questions about these Terms can be sent to{" "}
          <a href="mailto:bcmaharana@hotmail.com" className="underline">
            bcmaharana@hotmail.com
          </a>
          .
        </p>
      </LegalSection>
    </LegalPageLayout>
  );
}
