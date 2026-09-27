# Intended use and clinical safety draft

> Draft for review by qualified clinical, legal, and regulatory owners. This is
> not an approved product claim or regulatory determination.

## Proposed intended use

Care 360 organizes user-provided health information, appointments, prescribed
medication plans, nutrition preferences, and communication between users and
authorized care-team members. AI-assisted features provide educational or
professional decision support. They do not autonomously diagnose, prescribe,
triage, or replace professional judgment.

Care 360 SOS notifies configured Care 360 staff and connected clinicians. It
does not contact or dispatch emergency services. Immediate danger must be
directed to the user's local emergency number.

## Required clinical controls

1. Name a clinical safety officer and an emergency-operations owner.
2. Maintain a hazard log covering delayed/missed alerts, wrong-patient access,
   incomplete records, medication errors, allergen errors, hallucinated AI
   output, stale data, time-zone errors, and unavailable downstream providers.
3. Define severity, likelihood, detection, mitigation, verification evidence,
   residual risk, and acceptance authority for every hazard.
4. Validate patient and clinician workflows using representative records and
   edge cases. Record clinical reviewers, protocol, pass criteria, and results.
5. Require clinician review of source material before action. Never present AI
   confidence as clinical certainty.
6. Establish incident suspension and rollback criteria for SOS, prescriptions,
   record analysis, clinical search, and meal safety.
7. Review every public claim against the final regulatory classification in
   each market before publication.

## AI release checklist

- Version model, system instructions, safety rules, retrieval configuration,
  evaluation dataset, and consent disclosure together.
- Test prompt injection, cross-patient leakage, unsupported diagnosis,
  medication changes, self-harm/emergency content, allergens, pregnancy,
  pediatric cases, and conflicting records.
- Log model/version and safety outcome without logging unnecessary PHI.
- Provide deterministic fallbacks and a feature kill switch.
- Sample production outcomes under an approved privacy and clinical protocol.
