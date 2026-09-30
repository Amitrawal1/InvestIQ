// Who runs InvestIQ and how to reach them: used by the legal, About and Help pages.
// Change these in one place; the policies read them at render time.
export const SITE = {
  name: "InvestIQ",
  operator: "Amit Rawal",
  country: "India",
  contactEmail: "amit1032kumar@gmail.com",
  // Grievance Officer under the IT Rules 2021 / DPDP Act 2023 (an individual operator acts as their own)
  grievanceOfficer: "Amit Rawal",
  responseDays: 30,
};

// Bump when a policy's substance changes (shown as "Last updated" on each page)
export const POLICY_DATES = {
  privacy: "30 September 2026",
  terms: "30 September 2026",
  disclaimer: "30 September 2026",
};

export const mailto = (subject) =>
  `mailto:${SITE.contactEmail}${subject ? `?subject=${encodeURIComponent(subject)}` : ""}`;
