import React from "react";
import DocPage, { A, List, P, Strong, Table } from "../components/DocPage";
import { POLICY_DATES, SITE, mailto } from "../data/site";

// Written to match what the code actually does (backend/services/authService.js, portfolioService.js,
// docs/auth-and-portfolio.md). If data handling changes, update this page and POLICY_DATES.privacy.

const sections = [
  {
    id: "who-we-are",
    title: "Who we are",
    body: (
      <>
        <P>
          {SITE.name} is a stock research and screening website for Indian markets, operated by{" "}
          <Strong>{SITE.operator}</Strong>, an individual based in {SITE.country}. For this policy, the operator is the
          &ldquo;Data Fiduciary&rdquo; under India&rsquo;s Digital Personal Data Protection Act, 2023 (&ldquo;DPDP Act&rdquo;).
        </P>
        <P>
          This policy explains what personal data {SITE.name} collects, why, who it is shared with, how long it is kept,
          and the rights you have. It applies to the website and its API. Questions: <A href={mailto("Privacy question")}>{SITE.contactEmail}</A>.
        </P>
      </>
    ),
  },
  {
    id: "what-we-collect",
    title: "What we collect",
    body: (
      <>
        <P>We only collect what is needed to run your account and the features you choose to use.</P>
        <Table
          head={["Data", "When", "Why"]}
          rows={[
            ["Email address and display name", "You create an account", "To identify your account, sign you in and contact you about it"],
            ["Password (stored only as a salted scrypt hash)", "You sign up with email", "To verify your sign-in. We never store or see your password in plain text"],
            ["Google account ID, email and name", "You use “Continue with Google”", "To sign you in with Google. We do not receive your Google password"],
            ["Sign-in times (created, updated, last login)", "You use your account", "Account security and support"],
            ["Broker client ID and name", "You link Upstox or Zerodha", "To show which broker account is linked"],
            ["Broker access token (encrypted with AES-256-GCM)", "You link a broker", "To fetch your holdings with read-only access. It expires every day and is erased when you disconnect"],
            ["Holdings, positions, available funds and totals", "You sync a linked broker", "To show your portfolio with InvestIQ scores"],
            ["IP address", "You try to sign in", "Short-lived, in-memory rate limiting against password guessing. Not stored in our database"],
          ]}
        />
        <P><Strong>What we never collect:</Strong></P>
        <List
          items={[
            "Your broker password, PIN or OTP. You enter those only on Upstox's or Zerodha's own login page.",
            "Bank account, card or UPI details, PAN, Aadhaar or any government ID.",
            "The ability to trade. Broker access is read-only: InvestIQ cannot place, modify or cancel orders, or move money.",
          ]}
        />
      </>
    ),
  },
  {
    id: "browser-storage",
    title: "Cookies and browser storage",
    body: (
      <>
        <P>
          {SITE.name} does not use advertising or analytics cookies, tracking pixels or third-party analytics. We store two
          items in your browser&rsquo;s local storage, both strictly necessary:
        </P>
        <List
          items={[
            <><Strong>token</Strong>: your signed-in session (expires after 7 days, removed when you sign out).</>,
            <><Strong>investiq-theme</Strong>: your light, dark or system theme choice.</>,
          ]}
        />
        <P>
          If you use &ldquo;Continue with Google&rdquo;, Google&rsquo;s sign-in button may set its own cookies under
          Google&rsquo;s privacy policy. Page fonts are loaded from Google Fonts, which receives your IP address as part of
          that request.
        </P>
      </>
    ),
  },
  {
    id: "how-we-use",
    title: "How we use your data",
    body: (
      <>
        <P>We process your personal data on the basis of your consent, given when you create an account or link a broker, only to:</P>
        <List
          items={[
            "Create and secure your account, and sign you in.",
            "Fetch and display your linked portfolio, and match your holdings to InvestIQ company scores.",
            "Respond to your requests and support questions.",
            "Keep the service secure, for example by limiting repeated failed sign-ins.",
          ]}
        />
        <P>
          We do <Strong>not</Strong> sell or rent your data, use it for advertising, or use your portfolio to train
          models. Company rankings are built only from public market data, company filings and news, never from users&rsquo;
          portfolios.
        </P>
      </>
    ),
  },
  {
    id: "sharing",
    title: "Who we share it with",
    body: (
      <>
        <P>We use a small number of service providers (&ldquo;Data Processors&rdquo;) that process data on our behalf:</P>
        <Table
          head={["Provider", "Role", "Location"]}
          rows={[
            ["Vercel", "Hosts the website and API; keeps short-lived request logs", "Global edge network"],
            ["TiDB Cloud (PingCAP), on Amazon Web Services", "Database for accounts, broker links and portfolio snapshots", "Singapore"],
            ["Google", "“Continue with Google” sign-in, and web fonts", "Global"],
            ["Upstox / Zerodha", "Only if you link them: sign-in on their site and read-only portfolio data", "India"],
          ]}
        />
        <P>
          Because our database is in Singapore, your data is transferred outside India. This is permitted under the DPDP Act,
          and we will follow any restrictions the Government of India notifies. We may also disclose data if required by
          law, a court order or a lawful request from a government authority.
        </P>
      </>
    ),
  },
  {
    id: "retention",
    title: "How long we keep it",
    body: (
      <List
        items={[
          <><Strong>Account data</Strong>: until you delete your account.</>,
          <><Strong>Broker access tokens</Strong>: expire daily (Upstox at 3:30 AM IST, Zerodha at 6:00 AM IST) and are erased immediately when you disconnect.</>,
          <><Strong>Portfolio snapshots</Strong>: until you disconnect the broker with &ldquo;delete synced data&rdquo;, or delete your account.</>,
          <><Strong>Account deletion</Strong> removes your profile, broker links and all synced portfolio data from our live database straight away. Encrypted database backups kept by our provider may hold it for a limited period before they expire.</>,
        ]}
      />
    ),
  },
  {
    id: "security",
    title: "How we protect it",
    body: (
      <>
        <List
          items={[
            "All traffic is encrypted with HTTPS.",
            "Passwords are hashed with scrypt and a unique salt per user.",
            "Broker access tokens are encrypted at rest with AES-256-GCM and never sent back to your browser.",
            "Broker sign-in uses the brokers' own login pages with signed, time-limited requests.",
            "Every database query is parameterised, and repeated failed sign-ins are rate-limited.",
          ]}
        />
        <P>
          No system is perfectly secure. If a personal data breach affects you, we will notify you and the Data Protection
          Board of India as the DPDP Act requires.
        </P>
      </>
    ),
  },
  {
    id: "your-rights",
    title: "Your rights",
    body: (
      <>
        <P>Under the DPDP Act you can:</P>
        <List
          items={[
            <><Strong>Access</Strong> a summary of your data: use <A to="/settings#privacy">Settings → Privacy &amp; data → Download my data</A>.</>,
            <><Strong>Correct</Strong> it: edit your name and email in <A to="/settings#profile">Settings → Profile</A>.</>,
            <><Strong>Erase</Strong> it: disconnect a broker, or delete your account in <A to="/settings#delete-account">Settings → Delete account</A>.</>,
            <><Strong>Withdraw consent</Strong> at any time the same way. This does not affect processing already done.</>,
            <><Strong>Nominate</Strong> someone to exercise these rights if you die or become incapacitated.</>,
            <><Strong>Seek grievance redressal</Strong> from us, and then from the Data Protection Board of India.</>,
          ]}
        />
        <P>
          For anything you cannot do in Settings, email <A href={mailto("Data request")}>{SITE.contactEmail}</A> from your
          account email. We respond within {SITE.responseDays} days.
        </P>
      </>
    ),
  },
  {
    id: "children",
    title: "Children",
    body: (
      <P>
        {SITE.name} is meant for adults. You must be 18 or older to create an account, and we do not knowingly collect
        personal data from children. If you believe a child has created an account, contact us and we will delete it.
      </P>
    ),
  },
  {
    id: "changes",
    title: "Changes to this policy",
    body: (
      <P>
        We will update this page and its &ldquo;Last updated&rdquo; date when our data practices change. For significant
        changes, we will tell signed-in users on the website or by email before they take effect.
      </P>
    ),
  },
  {
    id: "grievance",
    title: "Contact and Grievance Officer",
    body: (
      <>
        <P>
          <Strong>Grievance Officer:</Strong> {SITE.grievanceOfficer}<br />
          <Strong>Email:</Strong> <A href={mailto("Grievance")}>{SITE.contactEmail}</A><br />
          <Strong>Country:</Strong> {SITE.country}
        </P>
        <P>
          We acknowledge grievances within 48 hours and resolve them within {SITE.responseDays} days. If you are not satisfied,
          you can complain to the Data Protection Board of India.
        </P>
      </>
    ),
  },
];

export default function Privacy() {
  return (
    <DocPage
      index="L1"
      label="Legal"
      title="PRIVACY POLICY"
      tabTitle="Privacy Policy"
      intro="What we collect, why, and the control you have over it."
      updated={POLICY_DATES.privacy}
      sections={sections}
    />
  );
}
