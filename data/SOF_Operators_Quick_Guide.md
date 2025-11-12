# SOF Method App — Operator’s Quick Guide

**Purpose:** Rapid screening of radionuclide mixtures via **Sum of Fractions (SOF)** against a limits table, with unit-safe conversions and an audit trail.  
**Important:** Screening tool only — **results require qualified professional review** prior to operational/regulatory use.

---

## 1) Inputs

### Samples file (CSV/Excel)
Required columns:
- `nuclide` — e.g., `Cs-137`, `Co-60` (aliases like `Cs137` will be canonicalized)
- `value` — numeric measurement
- `unit` — supported units (examples below)

Optional:
- `sigma` — 1-σ uncertainty, same unit as `value`

**Example (CSV):**
```

nuclide,value,unit,sigma
Cs-137,1.0,MBq,0.05
Co-60,600,"dpm/100 cm^2",

```

### Limits file (CSV/Excel)
Required columns:
- `nuclide`, `limit_value`, `limit_unit`

Optional:
- `category`, `rule_name`, `note`

**Example (CSV):**
```

nuclide,limit\_value,limit\_unit,category,rule\_name
Cs-137,4.0,MBq,General,My Limits v1
Co-60,2000,Bq/m^2,General,My Limits v1

```

---

## 2) Supported units (curated)

- **Activity:** `Bq`, `kBq`, `MBq`, `GBq`, `TBq`, `Ci`, `mCi`, `uCi`/`µCi`, `nCi`, `pCi`, `dpm`  
- **Dose:** `Sv`, `mSv`, `uSv`/`µSv`, `rem`, `mrem`  
- **Dose rate:** `Sv/h`, `mSv/h`, `uSv/h`, `rem/h`, `mrem/h`  
- **Time:** `s`, `min`, `h`, `d`, `yr`  
- **Surface contamination:** `.../100 cm^2` is **auto-normalized** to `Bq/m^2`.

> **Blocked for safety:** `counts`, `cpm`, `cps`.  
> Convert counts → activity with an efficiency/geometry method **before** using SOF.

---

## 3) Basic workflow (Desktop UI)

1. Launch:
```



```
2. **Load files:** drag-drop or Browse… (Samples, Limits).
3. (Optional) Pick **Category** (filters the limits table).
4. **Options:**
- **Combine duplicate nuclides** (sum; σ in quadrature)
- **Treat missing limits as zero** (skip) or raise error
- **Display sig figs** (UI formatting only)
- **Warn threshold** (e.g., 0.90) → drives amber banner
5. Click **Validate inputs** (catches missing headers, counts units).
6. Click **Compute SOF**.
7. Review **banner** and per-nuclide table (sortable).  
Save **CSV** results and **Audit JSON** as needed.

---

## 4) Banner logic (Pass/Color)

Let **SOF** be the total sum of per-nuclide fractions.

- **Red**: `SOF > 1.0` (Fail)  
- **Amber**: `SOF ≥ warn_threshold` **and** `SOF ≤ 1.0`  
- **Green**: `SOF < warn_threshold`

**Margin shown** = `1.0 − SOF`.

---

## 5) What’s computed

For each nuclide *i*:
- Convert sample measurement to **limit units**
- `fraction_i = measurement_i_in_limit_units / limit_value_i`
- If `sigma` provided: σ propagates; duplicates combine in quadrature
- **SOF** = `Σ fraction_i`

Table columns:
- **Nuclide**, **Conc** (converted), **Limit**, **Fraction**, **σ(fraction)** (if available),  
**Allowed addl (limit units)** = `max(0, (1 − SOF) × limit_value_i)`

---

## 6) Audit JSON (what it contains)

Created via **Save Audit JSON…**. Includes:
- **timestamp**, **app_version**
- **sof_summary**: `sof_total`, `sof_sigma`, `pass_limit`, `margin_to_1`, `category`, `rule_name`, `warn_threshold`
- **inputs**:
- `samples_path`, `limits_path`, `alias_path` (if set via `SOF_ALIAS_PATH`)
- `options`: `combine_duplicates`, `treat_missing_as_zero`, `display_sigfigs`, `warn_threshold`
- **file_integrity** (SHA-256): `samples`, `limits`, `aliases` (if provided)
- **results.summary**: assumptions, unmapped aliases, etc.

---

## 7) Tips & troubleshooting

- **Counts data present?** Convert to `dpm` or `Bq` first; counts units are blocked by design.
- **Surface units** like `dpm/100 cm^2` are accepted — they’ll display as `Bq/m^2`.
- **Sorting:** numeric columns sort properly (Conc, Limit, Fraction, σ, Allowed addl).
- **Aliases:** set once per session via environment:  
```



```
- **CSV format examples:** UI → **View examples…**.
- **Settings remembered** in:

---

## 8) Safety & scope

- Screening-level engineering tool (radiation protection / transport pre-analysis).  
- **Out of scope:** criticality, enrichment, weaponization, or safeguard bypass.  
- Use by qualified personnel; verify inputs/limits; retain the **Audit JSON** for traceability.

---
*App version:* v0.1.1 (working copies may show `0.1.2-dev`)
