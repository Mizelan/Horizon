# Evaluator Calibration

## 2026-05-08 youtube-source-provider

- evaluator_invocation_id: BF8F69EC-3591-4669-8A4D-E3337488D2AD
- topic: Provider metadata contract vs live-source proof readiness.
- severity calibration: Treat fake-only provider metadata tests as blocking when final_refresh requires real provider fields and code skips records without those fields. This is not a minor test-gap if the implementation mode itself is likely to suppress the required fields.
- applied default severity: required follow-up / blocking evaluator failure.

## 2026-05-08 youtube-source-provider repair round 2

- evaluator_invocation_id: 89F5631F-7E17-4632-92C9-064FB97B23BC
- topic: Re-evaluating provider metadata readiness after removing `--flat-playlist`.
- severity calibration: Once the implementation command no longer uses flat playlist mode and the focused test asserts `--flat-playlist` is absent, remaining live provider uncertainty belongs to final_refresh risk, not blocking admission.
- applied default severity: pass admission with non-blocking final_refresh follow-ups.
