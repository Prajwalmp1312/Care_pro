# Security and incident-response baseline

## Trust boundaries and high-risk assets

The mobile/web clients are untrusted. FastAPI enforces identity, session,
role, care relationship, consent, and file authorization. MySQL,
Redis, object/file storage, RAG indexes, email, AI, video, monitoring, and
administrative interfaces are separate trust boundaries. Highest-risk assets
are health records, messages, credentials/tokens, SOS events, clinician
identity, prescription data, signing secrets, database backups, and audit logs.

## Production controls

- TLS at every external and internal supported hop; HSTS at the trusted edge.
- Managed secrets, least-privilege identities, rotation, no shared admin users,
  MFA for workforce/admin accounts, and restricted break-glass access.
- Encrypted DB, Redis, object storage, snapshots, and backups with restore tests.
- Private database/cache networks, WAF/load balancer, egress controls, malware
  scanning/quarantine for uploads, and immutable audit retention.
- Redaction rules that exclude tokens, passwords, reset links, full request
  bodies, uploaded content, and unnecessary patient identifiers from logs.
- SAST, dependency, container, IaC, secret, and mobile-binary scans on every
  release; independent penetration testing before launch and after major change.

## Incident response

1. Maintain 24/7 security and clinical escalation contacts with tested paging.
2. Classify security, privacy, patient-safety, availability, and vendor events.
3. Contain using session revocation, credential rotation, feature kill switch,
   provider isolation, or rollback while preserving evidence.
4. Determine affected users/data/regions and meet contractual and statutory
   notification timelines with counsel and privacy leadership.
5. Conduct a blameless review, track corrective actions, update hazard/threat
   models, and verify fixes through tests and drills.

Quarterly exercises must include token theft, cross-patient authorization,
malicious upload, database restore, Redis loss, AI data disclosure, missed SOS,
and a compromised third-party processor.
