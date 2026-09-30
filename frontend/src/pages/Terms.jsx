import React from "react";
import DocPage, { A, List, P, Strong } from "../components/DocPage";
import { POLICY_DATES, SITE, mailto } from "../data/site";

const sections = [
  {
    id: "agreement",
    title: "Agreement",
    body: (
      <>
        <P>
          These Terms of Use (&ldquo;Terms&rdquo;) govern your use of the {SITE.name} website, API and related services
          (the &ldquo;Service&rdquo;), operated by {SITE.operator} in {SITE.country} (&ldquo;we&rdquo;, &ldquo;us&rdquo;). By
          creating an account or using the Service you agree to these Terms, our <A to="/privacy">Privacy Policy</A> and
          our <A to="/disclaimer">Investment Disclaimer</A>. If you do not agree, do not use the Service.
        </P>
      </>
    ),
  },
  {
    id: "service",
    title: "What the Service is and isn't",
    body: (
      <>
        <P>
          {SITE.name} provides research tools for Indian listed companies: market data, company financials, news with
          sentiment scores, model-based company rankings, and an optional read-only view of your own broker portfolio.
        </P>
        <P>
          <Strong>{SITE.name} is not investment advice.</Strong> We are not registered with SEBI as an Investment Adviser or
          Research Analyst, and nothing on the Service is a recommendation to buy, sell or hold any security. Scores and
          rankings are statistical screens that can be wrong. Read the full <A to="/disclaimer">Investment Disclaimer</A>.
        </P>
      </>
    ),
  },
  {
    id: "eligibility",
    title: "Eligibility and your account",
    body: (
      <List
        items={[
          "You must be at least 18 years old and able to form a binding contract under Indian law.",
          "Give accurate information and keep your email address up to date.",
          "Keep your password secure. You are responsible for activity on your account; tell us straight away if you suspect unauthorised use.",
          "One person, one account. Accounts are personal and may not be shared, sold or transferred.",
        ]}
      />
    ),
  },
  {
    id: "brokers",
    title: "Linking a broker",
    body: (
      <>
        <P>
          You may link an Upstox or Zerodha account. You sign in on the broker&rsquo;s own page, and the broker grants{" "}
          {SITE.name} <Strong>read-only</Strong> access to your profile, holdings, positions and funds. {SITE.name} cannot
          place orders or move money.
        </P>
        <List
          items={[
            "Link only broker accounts that you own.",
            "Your use of the broker remains governed by your agreement with that broker.",
            "Broker access expires every day under the brokers' rules, so you may need to reconnect.",
            "Portfolio figures come from the broker and may be delayed or incomplete. Your broker's own statements are the authoritative record.",
            "You can disconnect at any time in Settings.",
          ]}
        />
      </>
    ),
  },
  {
    id: "acceptable-use",
    title: "Acceptable use",
    body: (
      <>
        <P>You agree not to:</P>
        <List
          items={[
            "Scrape, crawl, bulk-download or systematically copy data, rankings or content from the Service, or use it to build a competing dataset or product.",
            "Resell, redistribute or publish the Service's data or scores commercially without our written permission.",
            "Probe, attack or disrupt the Service, bypass rate limits or security measures, or access other users' accounts or data.",
            "Reverse engineer the Service except where the law expressly allows it.",
            "Use the Service for anything unlawful, including market manipulation or spreading misleading information about securities.",
          ]}
        />
      </>
    ),
  },
  {
    id: "data-sources",
    title: "Data and third-party content",
    body: (
      <P>
        Market prices, company filings and announcements come from third parties such as NSE and Upstox. We process them
        automatically and do not guarantee that they are accurate, complete or timely. Prices may be delayed, filings may be
        parsed incorrectly, and automated sentiment labels can misread news. Always check important information against the
        original source.
      </P>
    ),
  },
  {
    id: "ip",
    title: "Intellectual property",
    body: (
      <P>
        The Service, including its design, software, scores, rankings and text, belongs to us or our licensors. You may use
        it for your own personal, non-commercial research. Third-party data remains the property of its owners.
      </P>
    ),
  },
  {
    id: "availability",
    title: "Availability and changes",
    body: (
      <P>
        The Service is provided free of charge and on an &ldquo;as is&rdquo; and &ldquo;as available&rdquo; basis. We may
        change, pause or discontinue any feature, including rankings methods and data sources, at any time. Live data
        depends on third-party services and may be unavailable.
      </P>
    ),
  },
  {
    id: "liability",
    title: "Limitation of liability",
    body: (
      <>
        <P>
          To the fullest extent permitted by law, we make no warranties, express or implied, about the Service, including
          fitness for a particular purpose, accuracy or uninterrupted availability.
        </P>
        <P>
          We are not liable for any investment decision you make or any trading loss, lost profit, or indirect, incidental or
          consequential damage arising from your use of, or inability to use, the Service. Where liability cannot be
          excluded, our total liability is limited to ₹1,000. Nothing in these Terms limits rights you have that cannot be
          waived under Indian law, including the Consumer Protection Act, 2019.
        </P>
      </>
    ),
  },
  {
    id: "indemnity",
    title: "Indemnity",
    body: (
      <P>
        You agree to indemnify us against claims, losses and costs arising from your breach of these Terms or your misuse of
        the Service.
      </P>
    ),
  },
  {
    id: "termination",
    title: "Ending your use",
    body: (
      <P>
        You can stop using the Service and delete your account at any time in <A to="/settings#delete-account">Settings</A>.
        We may suspend or close accounts that breach these Terms or put the Service or other users at risk, and will tell
        you why unless the law prevents us.
      </P>
    ),
  },
  {
    id: "law",
    title: "Governing law and disputes",
    body: (
      <P>
        These Terms are governed by the laws of India. Please contact us first so we can try to resolve any dispute
        informally. Otherwise, disputes are subject to the jurisdiction of the courts of India.
      </P>
    ),
  },
  {
    id: "changes",
    title: "Changes to these Terms",
    body: (
      <P>
        We may update these Terms. The &ldquo;Last updated&rdquo; date shows the current version. For material changes, we
        will give signed-in users notice before they take effect. Continuing to use the Service after that means you accept
        the new Terms.
      </P>
    ),
  },
  {
    id: "contact",
    title: "Contact",
    body: (
      <P>
        Questions about these Terms: <A href={mailto("Terms of Use")}>{SITE.contactEmail}</A>.
      </P>
    ),
  },
];

export default function Terms() {
  return (
    <DocPage
      index="L2"
      label="Legal"
      title="TERMS OF USE"
      tabTitle="Terms of Use"
      intro="The rules for using InvestIQ, in plain language."
      updated={POLICY_DATES.terms}
      sections={sections}
    />
  );
}
