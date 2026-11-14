# Medication Coverage Search

Provider-facing medication coverage and prior-authorization reference for three AHCCCS Complete Care plans: Arizona Complete Health, Banner — University Family Care ACC, and UnitedHealthcare ACC.

[Open the app](https://dbpower-max.github.io/medication-coverage-pa/)

Search by medication, plan, category and coverage status. Results include source-linked preference, explicit PA requirements, step therapy, quantity limits and available policy text. Absence from results does not establish noncoverage. Arizona Complete Health additional-plan data and some source identity conflicts remain incomplete.

## Run locally

Requires Python 3.12+ and a modern browser.

```bash
python tools/build_provider_site.py
python -m http.server 8000 --directory _site
```

Open http://localhost:8000. The build includes only the three plans and their linked provider sources; historical and other-plan repository material is excluded. Large Banner PA criteria link to the official payer PDF, with indexed policy text bundled locally.

## Publish

GitHub Pages uses the GitHub Actions publishing source. The `Publish provider app` workflow builds and validates the scoped site, then deploys `_site` on pushes to `main` or manual runs. No application API key is required.
