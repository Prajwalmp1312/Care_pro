# Privacy, processors, and retention working document

> This is an engineering control map, not a published Privacy Policy or legal
> advice. Counsel and the privacy officer must approve the final policy,
> retention schedule, consent language, and regional rights process.

## Data inventory

Document purpose, legal basis, sensitivity, owner, storage, encryption,
processors, recipients, retention, deletion method, and audit evidence for:

- identity, clinician credentials, sessions, IP addresses, and security events;
- demographics, medical records, extracted text, summaries, RAG embeddings,
  prescriptions, appointments, messages, attachments, and notifications;
- emergency alerts, consent versions, ownership, escalation, and response logs;
- nutrition profiles, allergies, cycle data, meal plans, feedback, and chat;
- backups, logs, support tickets, analytics, crash reports, and email delivery.

## Processor register

Before launch, record contract/BAA/DPA status, regions, subprocessors, retention,
security contacts, and exit/export procedures for hosting, MySQL, Redis, object
storage, email, Gemini/Google, Comm360, monitoring, crash reporting, support,
analytics, CDN/WAF, and app stores. Disable any processor that has not passed
privacy and security review.

## Deletion workflow

The API now records a reauthenticated deletion request, disables the account,
and revokes sessions. Production still requires a privacy worker and runbook to:

1. verify request identity and applicable jurisdiction;
2. place records subject to legal hold or clinical retention in restricted
   storage with the governing rule and expiry;
3. delete or de-identify eligible relational rows, files, derived text,
   embeddings, notifications, caches, search indexes, processor copies, and
   backups according to the approved schedule;
4. record each deletion action without retaining unnecessary deleted content;
5. notify the requester and support exceptions/appeals within the published SLA.

No release may describe deletion as complete until this worker is implemented,
tested across every store, and reviewed by privacy/legal owners.
