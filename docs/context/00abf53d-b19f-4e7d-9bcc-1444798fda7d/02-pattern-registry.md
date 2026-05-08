# Pattern Registry

## 2026-05-08 - Mock-heavy final_refresh integration overclaim

When a final_refresh proof is labeled as "focused integration", the command must exercise a real cross-module path. Unit tests that monkeypatch the external subprocess edge are acceptable only if the Horizon-side config, factory, client, and analyzer path remains real. If the suite monkeypatches internal builders or runs isolated unit surfaces only, final_refresh can pass without proving the integration claim.

## 2026-05-08 - Duplicate plan schema drift

When a sprint artifact and a same-topic root plan both exist, field vocabulary drift can mislead later repair agents. The approved artifact must either align the duplicate plan or mark it historical/non-authoritative before generator dispatch.

## 2026-05-08 - Active design artifact schema drift after root-plan demotion

When repairing duplicate plan schema drift, scan every markdown artifact in the active artifact directory, not only the root duplicate plan and approved sprint plan. A demoted root plan does not protect final_refresh admission if a sibling design artifact still presents stale field names as active architecture.

## 2026-05-08 - Field-name repair can leave type/default drift

When repairing stale config schema names, also compare active design field types, defaults, and ownership semantics against implementation and user-facing docs. A design artifact can stop mentioning obsolete field names while still advertising an invalid replacement shape, such as a list-shaped command default where the implemented model accepts a string command name.

## 2026-05-08 - Optional-only pytest can spoof dependency failures

When final_refresh uses plain `uv run pytest`, verify that pytest resolves inside the project environment. If pytest exists only in optional extras, `uv run pytest` can fall through to a system pytest and misreport installed project dependencies, turning an environment selection issue into a false missing-dependency diagnosis.
