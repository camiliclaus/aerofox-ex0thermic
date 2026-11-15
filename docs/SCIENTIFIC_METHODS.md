# Scientific methods

## Units and atmosphere

Pressures are converted to kPa (1 atm = 101.325 kPa; 1 psi = 6.894757 kPa; 1 mmHg = 0.133322 kPa). O₂ is stored as a mole
fraction *X*O₂ (0–1); percentages are converted, never mixed. O₂ partial pressure *p*O₂ = *X*O₂ · *p*.
"Tested near" an atmosphere means |Δp| ≤ 10 kPa and |ΔX| ≤ 0.03.

## FLEX burning-rate constant

d²-law: *d*²(*t*) = *d*₀² − *K t* (Eq. 1). *K* is refitted for each DropletData file by ordinary least squares on
0.2 *t*b ≤ *t* ≤ 0.9 *t*b, where *t*b is the tabulated visible burn time; the post-extinction rate uses
*t*b + 0.5 s … *t*b + 0.5 s + 0.5 *t*b (≥ 10 samples). Files are joined to table rows through the official FLEX number
obtained from the CIR identifier in NASA/TP-2015-216046.

Descriptive regression per fuel: *K* = β₀ + β₁ *X*O₂ + β₂ ln(*p*/1 atm) + β₃[CO₂] + β₄[He] + ε, OLS, with 95 % intervals from
2,000 bootstrap resamples of tests. Not predictive: the design is non-factorial and droplet size is pooled.

## Compartment tracer model

For fixed-volume, well-mixed compartments *i* with volume *V*ᵢ, inter-compartment flows *Q*ᵢⱼ (from *i* to *j*), clean supply
*S*ᵢ, exhaust *E*ᵢ and source *G*ᵢ(*t*):

*V*ᵢ d*C*ᵢ/d*t* = Σⱼ *Q*ⱼᵢ *C*ⱼ − (Σⱼ *Q*ᵢⱼ + *E*ᵢ) *C*ᵢ + *G*ᵢ(*t*)      (Eq. 2)

with volume conservation *S*ᵢ + Σⱼ *Q*ⱼᵢ = *E*ᵢ + Σⱼ *Q*ᵢⱼ enforced (inputs violating it are rejected). Integrated with backward
Euler (unconditionally stable; tracer mass conserved to round-off) or RK4.

**Verification** (tests/test_science.py): single compartment vs *C*₀ e^(−*Qt/V*) (max error < 5×10⁻³ implicit at Δt = 1 s,
< 10⁻⁶ RK4); first-order convergence of backward Euler (error ratio ≈ 2 per halving of Δt); steady state *C* = *G/Q*;
mass balance error < 10⁻⁹ in the example network. **Validation:** none against fire measurements — the model describes
mixing of a passive tracer only, not fire growth, toxicity, detector alarm logic or suppression. Example scenarios are
labelled synthetic.

## Saffire-II flow reconstruction

Telemetry workbook PSI-99, sheet RawData (1 Hz; the `RelativeSeconds` column is in ms). Ignition time of sample *k* = first
record where `Sample{k}IgniterI` leaves its baseline state (value > −1). Measured flow = mean of each anemometer over
0–120 s after ignition.

## SAME-R

Per-test moments from the PSI-101 results workbook (reduced data sheet); arithmetic mean diameter AMD = M1/M0. Zero moments
are treated as not measured. Group medians and IQR by material; Spearman ρ for aging trends.

## Evidence coverage and fire-safety factors

Coverage codes: *direct* (measured in the decision's regime), *partial* (different regime, conditions only, or
literature), *none*. Factor ordering (`data/curated/fire_factors.json`): Tier 1 if implicated in a fatal or mission-ending
NASA fire/oxygen incident in the evidence base **and**, for the atmosphere factor, if the design condition is outside tested
conditions (|Δp| > 10 kPa from 101.3 kPa, O₂ > 23.5 %, or lunar/Mars gravity); otherwise Tier 2/3. These are qualitative
rules shown with every matrix; no numeric risk scores are produced.

## Applicability score (retrieval)

Mean over available dimensions of: gravity match (1 same; 0.3 partial-gravity scenario vs micro/Earth evidence; 0.4 other);
pressure 1 − 2|Δp|/p; O₂ 1 − |ΔO₂|/10 points. Neutral 0.5 when nothing can be compared. Final rank = BM25 × kind weight ×
(0.5 + applicability).

## Verification vs validation in AeroFox

| Term | Meaning here | Where |
|---|---|---|
| Numerical verification | code solves the stated equations correctly | compartment tests, unit tests |
| Data verification | processed tables reproduce independent sources | FLEX K refits, test-sheet agreement, checksums |
| Physical validation | model agrees with experiments | not claimed for the tracer model |
| Calibration | parameters tuned to data | none |
| Uncertainty quantification | bootstrap CIs, fit standard errors, IQRs | notebook, findings |
