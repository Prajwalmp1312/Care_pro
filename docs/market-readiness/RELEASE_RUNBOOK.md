# Production release runbook

## Before release

- Obtain signed approvals for every P0 gate in `MARKET_READINESS.md`.
- Pin immutable image/artifact versions and generate an SBOM.
- Set `ENVIRONMENT=production`, strong `SECRET_KEY`, HTTPS frontend/origins,
  least-privilege TLS MySQL credentials, `REDIS_URL`,
  `REQUIRE_SHARED_RATE_LIMITER=true`, pool sizes, and provider secrets.
- Run API replicas with `RUN_BACKGROUND_SCHEDULERS=false`; run exactly one
  scheduler deployment with it enabled until the loops are moved to a durable
  job system.
- Configure mobile production HTTPS API, privacy, terms, and support URLs in EAS
  secrets. Confirm cleartext traffic is false in the built manifests.
- Run backend, web, Android, iOS, authorization, migration, backup/restore,
  failover, load, accessibility, and clinical-safety test suites.

## Deploy and verify

1. Back up and record restore point; deploy additive migrations first.
2. Deploy API canary; verify `/api/health/live` and `/api/health/ready` from the
   load balancer and check DB/Redis saturation and error rate.
3. Deploy scheduler singleton and verify reminder/SOS claims are not duplicated.
4. Deploy web, then staged mobile rollout. Exercise login, consent, one patient
   and clinician flow, session revocation, one notification, and support links.
5. Observe error, latency, saturation, SOS, email, and privacy-request queues.

## Rollback

Stop rollout, disable affected features, roll back application artifacts, and
avoid destructive schema reversal. Preserve audit evidence. If patient safety
or privacy may be affected, invoke the incident process and notify the named
clinical/privacy owners. Validate restored behavior before reopening traffic.
