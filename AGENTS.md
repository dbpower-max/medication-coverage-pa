# Project decisions

Start with Decision lookup in the current Med coverage/PA Master Ledger in the project workspace. It links to the decision register and the owning audit rows. Use those records across sessions, including scheduled work.

- Before changing a card, source mapping or workflow, find the applicable decision IDs and any later, narrower exception. Use the recorded evidence for the exact plan, product and source date. Reopen a settled question only when new evidence, a safety issue or an explicit clinician update changes its basis.
- For each change, identify the intended difference and the existing behavior it must preserve. Include the decision IDs and an observable acceptance check in the pull request or existing audit handoff. For layout changes, check placement in the browser at desktop and mobile widths. For source changes, exercise the affected evidence scopes and the nearest unaffected case.
- Follow the current session’s authorization. Keep clinical sign-off, source verification and release status distinct. If a material conflict remains unresolved, record it with both references and continue independent work.
- When a rule changes, update its existing ledger entry with the effective date, scope, evidence, exceptions and any superseded decision. Keep record-level evidence in the owning workbook. Store only the decision IDs and the verification result in a public change description.
