---
paths:
  - "rules/**"
---
- Rule files must validate against `rules/schema/rule.schema.json`; fact keys must exist in `rules/facts.yaml`.
- Files in `rules/published/` require `review.reviewed_by` and `review.reviewed_on`; never fill these in yourself.
- Never invent legal content (thresholds, dates, forms, penalties). Leave `TODO(CA):` markers for the owner/CA.
- A rule change requires scenario changes in `rules/scenarios/` covering applies and not_applicable.
