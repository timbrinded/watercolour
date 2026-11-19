"""The quality gates that every change to the engine is held to, calibrated against the 0.8.0 rig.

Every gate is defined here and nowhere else, so that a change to any threshold shows in one diff. A gate states in
words what it measures, in which scenario, against what threshold and on what authority, and carries the checks
that calibration.py (and benchmark.py, for performance) evaluate. Thresholds are never edited to fit a result: a
threshold believed wrong is reported with evidence.

Gates of the item "global" apply to every change. Gates that two approved items asked for in the same form are
merged into one, keeping every condition either asked for; merged_from names the reviewed gates each one replaces.

A check compares one measurement, named "<scenario>.<measurement>", with a bound:

    "<=", "<", ">=", ">", "=="   compare with the bound; a list passes when every element does
    "between"                     lies within the closed interval (low, high)
    "near"                        differs from the baseline value by at most the bound
    "increasing", "decreasing"    a list that rises (falls) strictly; "nondecreasing" may also stay level

With scale "baseline" the bound is multiplied by the measurement's value on the 0.8.0 baseline (element by element
for a list); with "baseline_plus" it is added to it. A measurement that is missing or None fails its check.
"""

from dataclasses import dataclass

Bound = float | int | bool | str | tuple[float, float] | tuple[()] | None

ITEMS = ("flow_exponent", "binder", "ordered_layers")
KINDS = ("physical", "invariant", "regression", "compatibility", "performance")


@dataclass(frozen=True)
class Check:
    metric: str
    op: str
    bound: Bound = None
    scale: str = "absolute"


@dataclass(frozen=True)
class Gate:
    id: str
    item: str  # one of ITEMS, or "global" for a gate that applies to every change
    kind: str
    metric: str
    scenario: str
    comparator: str
    threshold: str
    source: str
    checks: tuple[Check, ...]
    expected_on_baseline: str = "pass"
    merged_from: tuple[str, ...] = ()
    extended: bool = False  # too long for the standard run: selected by id or with --extended
    correction: str = ""  # how the gate differs from the reviewed one, and why


def within(metric: str, low: float, high: float) -> Check:
    """The measurement lies within (low, high) times its 0.8.0 value."""
    return Check(metric, "between", (low, high), "baseline")


GATES: tuple[Gate, ...] = (
    # ------------------------------------------------------------------------------------------ global: invariants
    Gate(
        id="I-water-conservation",
        item="global",
        kind="invariant",
        metric="Relative change in the water of the film with evaporation and absorption off; and relative change in "
        "all the water (film, paper and masking fluid) with only evaporation off, while the film soaks into the "
        "paper and spreads through it",
        scenario="Three mop-16 strokes of ultramarine 0.05 and, separately, 4.0 (strong paint thickens the film), "
        "then a wait of 5 s (test_flow_alone_conserves_water); three mop-16 strokes of ultramarine 0.6 with the "
        "film's and the paper's evaporation off, then a wait of 30 s, summed in double precision",
        comparator="<=",
        threshold="1e-4 for each film; 1e-6 for all the water",
        source="Conservation law; existing test. Flow I1 measured 0.0 for h3f; the binder repeated it with strong "
        "paint. All the water: 0.8.0 1.3e-9 while 24% of the film soaks in, so 1e-6 leaves float32 rounding a "
        "margin of several hundred.",
        checks=(
            Check("flow_conserves_water.water_change_0.05", "<=", 1e-4),
            Check("flow_conserves_water.water_change_4", "<=", 1e-4),
            Check("flow_conserves_water.water_and_paper_change", "<=", 1e-6),
        ),
        merged_from=("flow_exponent:I1-water-conservation", "binder:I2-water-and-pigment-conserved (water)"),
        correction="The reviewed gates count only the film, with absorption off, so water lost or made between the "
        "film and the paper, or in the paper's own spreading, went unseen; all the water is now counted with the "
        "exchange running.",
    ),
    Gate(
        id="I-pigment-conservation",
        item="global",
        kind="invariant",
        metric="Relative change of pigment: on the sheet as a deep puddle drains; on the sheet plus in the brush as a "
        "nearly empty brush works wet paint, and as brushes lift paint; and of suspended + deposited + mask_pigment "
        "over a brush-free advance",
        scenario="test_pigment_is_conserved_as_a_deep_puddle_drains; test_brush_and_sheet_together_conserve_pigment; "
        "a damp flat 8 passed three times over two dried flat-12 strokes of quinacridone rose 1.0 and left 10 s, and "
        "a drained round 3 drawn twice through a mop wash of ultramarine 1.5 at film 0.12 (no tissue); the 48 px "
        "layered scene (umber band, white line, phthalo glaze, part dried) advanced 30 s",
        comparator="<=",
        threshold="1e-4 (puddle); 0.01 (brush and sheet); 1e-4 (lifting, in double precision); 1e-6 (brush-free "
        "advance, in double precision)",
        source="Conservation of pigment; the existing tests' thresholds; ordered INV-1 measured 8.4e-9. Lifting: the "
        "bound of test_scrubbing_paint_that_hardly_stains_lifts_no_more_than_lies_on_the_paper; 0.8.0 3.7e-9 and "
        "2.3e-10.",
        checks=(
            Check("puddle_drains.pigment_change", "<=", 1e-4),
            Check("brush_and_sheet.relative_change", "<=", 0.01),
            Check("lift_conserves_pigment.dried_change", "<=", 1e-4),
            Check("lift_conserves_pigment.wet_change", "<=", 1e-4),
            Check("advance_conserves_pigment.pigment_change", "<=", 1e-6),
        ),
        merged_from=(
            "flow_exponent:I2-pigment-conservation",
            "binder:I2-water-and-pigment-conserved (pigment)",
            "ordered_layers:INV-1-conservation",
        ),
        correction="No reviewed gate counted pigment through a lifting stroke, the path where the hairs loosen and "
        "wipe up settled paint: it is where the scrub fault made pigment from nothing, and the path the binder "
        "changes (P2, P3). It is now counted, sheet and brush together.",
    ),
    Gate(
        id="I-sound-state",
        item="global",
        kind="invariant",
        metric="Values of any state field that are not finite or are negative, and cells where 0 <= lowest <= "
        "underlying <= deposited fails, summed over every scenario of the run",
        scenario="Checked at the end of every painting and experiment that runs, always including: the draining "
        "puddle, deep water and thin films on damp paper, the slope runs, a deep puddle of rose 6.0 deep with "
        "pigment 40 (and gum at GUM_SET) left 30 s, scrubbed with a clean round 8, then dried, rewetted and scrubbed",
        comparator="==",
        threshold="0",
        source="Physical bounds (amounts cannot be negative) and the definition of the cumulative layers.",
        checks=(
            Check("soundness.unsound_cells", "==", 0),
            Check("deep_puddle_scrubbed.unsound_cells_wet", "==", 0),
            Check("deep_puddle_scrubbed.unsound_cells_rewetted", "==", 0),
        ),
        merged_from=(
            "flow_exponent:I3-finite-non-negative",
            "binder:I4-finite-non-negative",
            "ordered_layers:INV-2-ordered-finite",
        ),
        correction="INV-2 asked for the check after every advance; it is made at the end of every scenario and of "
        "every saved state that the compatibility scenario loads, which keeps the suite within its time.",
    ),
    Gate(
        id="I-determinism",
        item="global",
        kind="invariant",
        metric="Largest absolute difference over every state field and the value view between two identical runs",
        scenario="The mop wash (ultramarine 0.6) with a stroke of cadmium red 4.0 drawn in, waited 6 s, twice on the "
        "default device; the pool and dab of tests/test_together.py at 96 px, twice on the CPU",
        comparator="==",
        threshold="0 (bitwise)",
        source="Engine contract: replayable, scored paintings. Measured 0 for h3f on CUDA and for the gum "
        "prototype on the CPU.",
        checks=(
            Check("determinism_and_batching.repeat_difference", "==", 0.0),
            Check("determinism_and_batching.cpu_repeat_difference", "==", 0.0),
        ),
        merged_from=(
            "flow_exponent:I4-determinism",
            "binder:I5-determinism",
            "ordered_layers:INV-3-determinism-and-resume (determinism)",
        ),
    ),
    Gate(
        id="I-batched-equals-single",
        item="global",
        kind="invariant",
        metric="Largest absolute difference over every state field and the value view between a sheet painted "
        "alone and the same sheet in a batch of two; relative mean difference of water, suspended, deposited "
        "(and gum) for the pool and dab of tests/test_together.py",
        scenario="The determinism script on seeds 3 and 4 through SharedClock and SheetBatch against each alone; "
        "the pool and dab on seeds 1 and 2 at 96 px; the 48 px layered scene (umber band dried, white line over it "
        "dried, phthalo glaze across both) on seeds 5 and 6, the second begun 30 s late, each compared as its "
        "script ends",
        comparator="<= / <",
        threshold="1e-6 (largest absolute, both); 1e-3 (relative mean, pool and dab)",
        source="Engine contract of together.py and tests/test_together.py. Measured 0.0 for h3f and for the "
        "layered prototype. 0.8.0 gives 0.0 for the layered scene begun late.",
        checks=(
            Check("determinism_and_batching.batched_difference", "<=", 1e-6),
            Check("determinism_and_batching.pool_batched_relative_difference", "<", 1e-3),
            Check("layered_batching.difference", "<=", 1e-6),
        ),
        correction="The merged scenarios lay no paint over set paint, so no layer opens in them and the layer fields "
        "of ordered INV-4 were compared only as zeros; and their sheets are always in the same stage of drying. The "
        "layered scene of INV-4 is added, with its two sheets in different stages, the case where a step taken for "
        "one sheet's sake could change the other's.",
        merged_from=(
            "flow_exponent:I5-batched-equals-single",
            "binder:I6-batched-equals-single",
            "ordered_layers:INV-4-batched-equals-single",
        ),
    ),
    Gate(
        id="I-save-and-resume",
        item="global",
        kind="invariant",
        metric="Largest absolute difference over every state field and the value view between a session cut short "
        "mid-wait and reopened, and the same session run without a break; and between a sheet and a fresh sheet "
        "loaded from its saved state, before and after both advance 3 s",
        scenario="64 px session: flat-8 burnt umber 3.0 stroke, dried; round-4 opaque white 4.5 across it and a "
        "wait of 12 s, saved after every span of the wait (SAVE_INTERVAL 0) and stopped after the fifth save",
        comparator="==",
        threshold="0 (bitwise); the second pass resumes after its two completed actions; clocks equal",
        source="Session replay contract (state is restored, not replayed). Anything the engine derives on load "
        "rather than saves must give the same continuation, so resume equivalence is shown, not assumed.",
        checks=(
            Check("session_resume.resumed_from_action", "==", 2),
            Check("session_resume.session_difference", "==", 0.0),
            Check("session_resume.clocks_equal", "==", True),
            Check("session_resume.loaded_difference", "==", 0.0),
            Check("session_resume.continued_difference", "==", 0.0),
        ),
        merged_from=("ordered_layers:INV-3-determinism-and-resume (resume)",),
    ),
    Gate(
        id="I-unmoved-paint-unchanged",
        item="global",
        kind="invariant",
        metric="Largest change in value of dried white-over-dark columns after each of two clear-water wettings",
        scenario="rewet_still: white 6.0 columns over the dried dark band, dried; resolubility 0 and water 0.3 set on "
        "the band, so deposits move by no more than rounding; wait 2 s and dry, twice",
        comparator="<=",
        threshold="1e-3 (and deposits moved by at most 1e-5, the scenario's premise)",
        source="Bookkeeping identity: paint that has not moved looks the same. Measured: 0.8.0 0, prototype 0. The "
        "premise: a deposit of 1e-5 changes the value by about 1e-5, a hundredth of the bound, so paint that moved "
        "that little cannot account for a failure.",
        checks=(
            Check("rewet_without_moving_paint.value_change", "<=", 1e-3),
            Check("rewet_without_moving_paint.deposit_moved", "<=", 1e-5),
        ),
        merged_from=("ordered_layers:INV-6-no-layer-without-new-paint",),
        correction="The premise was 'deposits moved by at most 1e-8', which 0.8.0 meets with 7.7e-9 on paper seed "
        "3 but not on seed 4 (2.4e-8) or seed 5 (1.9e-7): rounding, appearing in cells that held no paint, at a "
        "level any change to the engine's arithmetic can cross. It is now 1e-5, still a hundredth of the value bound.",
    ),
    # ------------------------------------------------------------------------------------------ global: compatibility
    Gate(
        id="C-continue-0.8.0-painting",
        item="global",
        kind="compatibility",
        metric="Paintings begun and saved by 0.8.0 open under the engine, their logs verify, their totals and "
        "pictures are those saved, and they carry on with sound fields",
        scenario="Begun with the 0.8.0 package in its own process: a 128 px mop wash left wet (continued with a "
        "cadmium stroke and a 20 s wait); a 64 px rose stroke (a further stroke, reopened); a 64 px umber stroke, "
        "dried (opened, then white 4.5 laid across it and dried, reopened)",
        comparator="==",
        threshold="Water and pigment totals equal those saved; value view bitwise equal to 0.8.0's; no layers on "
        "load; 2 strokes counted; all fields finite and >= 0; every state field saved",
        source="Compatibility rule: a painting is restored, not replayed, and a 0.8.0 painting follows one rule.",
        checks=(
            Check("paintings_begun_with_reference.wet_water_equal", "==", True),
            Check("paintings_begun_with_reference.wet_pigment_equal", "==", True),
            Check("paintings_begun_with_reference.wet_unsound_cells", "==", 0),
            Check("paintings_begun_with_reference.rose_strokes_counted", "==", 2),
            Check("paintings_begun_with_reference.dried_value_difference", "==", 0.0),
            Check("paintings_begun_with_reference.dried_layer_total", "==", 0.0),
            Check("paintings_begun_with_reference.dried_unsound_cells", "==", 0),
            Check("paintings_begun_with_reference.saved_fields_complete", "==", True),
        ),
        merged_from=(
            "flow_exponent:C1-session-continues",
            "binder:C2-old-session-continues",
            "ordered_layers:COMP-1-load-0.8.0",
            "ordered_layers:COMP-2-continue",
        ),
        correction="COMP-2 also asked that white laid over the 0.8.0 umber show lighter than the umber by more than "
        "0.2. On 0.8.0 it is lighter by 0.180 (0.527 against 0.347): the margin comes from layering, which 0.8.0 "
        "does not have, so that check moved to the ordered-layers gate COMP-2-white-over-continued-painting.",
    ),
    Gate(
        id="C-vocabulary-unchanged",
        item="global",
        kind="compatibility",
        metric="session.py, cli.py, studio.py and brushes.py; the session's action kinds and its verdict on "
        "reference passes; the CLI arguments; Sheet.STATE_FIELDS; the SimulationParameters field names and "
        "defaults; every property of every paint; the paper made from a seed",
        scenario="Static comparison against the 0.8.0 package, Session._validate of 13 reference passes, and a "
        "64x96 paper (seed 3) generated by both on the CPU",
        comparator="==",
        threshold="Files byte-identical; actions, verdicts and arguments identical; every 0.8.0 state field kept; "
        "new state fields only gum, underlying and lowest, each optional on load; parameter names identical; every "
        "0.8.0 parameter default, paint property and paper field identical",
        source="Compatibility rule: no new or changed action, and a 0.8.0 painting loads. The approved designs add "
        "the gum field (binder) and the underlying and lowest layers (ordered layers), and no age state "
        "(Daniels and Shashoua 1993: insolubility appears only after ageing at 60-100 C). None of them changes a "
        "paint, the paper or a parameter's default, so a gate met by retuning one is met for the wrong reason.",
        checks=(
            Check("vocabulary.changed_files", "==", ()),
            Check("vocabulary.actions_equal", "==", True),
            Check("vocabulary.validation_equal", "==", True),
            Check("vocabulary.arguments_equal", "==", True),
            Check("vocabulary.state_fields_kept", "==", True),
            Check("vocabulary.new_state_fields_approved", "==", True),
            Check("vocabulary.new_state_fields_optional", "==", True),
            Check("vocabulary.parameters_equal", "==", True),
            Check("vocabulary.parameter_defaults_kept", "==", True),
            Check("vocabulary.pigments_kept", "==", True),
            Check("vocabulary.paper_kept", "==", True),
        ),
        merged_from=(
            "flow_exponent:C2-vocabulary-unchanged",
            "binder:C3-vocabulary-unchanged",
            "binder:C4-no-age-state",
            "ordered_layers:COMP-3-vocabulary-suite-hygiene (session.py untouched)",
        ),
        correction="The flow gate asked for Sheet.STATE_FIELDS identical to 0.8.0 and the binder gate for no field "
        "beyond 0.8.0's but gum; in one pull request with all three items these become: new fields only those the "
        "approved items declare (gum, underlying, lowest). Added in audit: paint, paper and parameter defaults "
        "unchanged. Several gates have absolute thresholds that a retuned constant meets without the mechanism: "
        "PHY-6 (0.8.0 0.386 and 0.475 against 0.50 and 0.60) and COMP-2-white-over-continued-painting (0.180 "
        "against 0.2) by a more opaque white, regression gates by a re-set evaporation or flow rate.",
    ),
    Gate(
        id="C-hygiene",
        item="global",
        kind="compatibility",
        metric="ruff check, ruff format --check and pyrefly check over the repository; reads of the environment in "
        "src/watercolor",
        scenario="The tools of the project's own environment, run from the repository root",
        comparator="==",
        threshold="All clean; no environment reads",
        source="Task rules and house style; the layered prototype read WATERCOLOR_LAYERS at import.",
        checks=(
            Check("hygiene.lint_clean", "==", True),
            Check("hygiene.format_clean", "==", True),
            Check("hygiene.types_clean", "==", True),
            Check("hygiene.environment_reads", "==", 0),
        ),
        merged_from=("ordered_layers:COMP-3-vocabulary-suite-hygiene (hygiene)",),
    ),
    # ------------------------------------------------------------------------------------------ global: regressions
    Gate(
        id="R-test-suite",
        item="global",
        kind="regression",
        metric="Failures in tests/ other than tests/test_calibration.py",
        scenario="pytest -q tests on the default device",
        comparator="==",
        threshold="0 failures (58 tests at 0.8.0)",
        source="Existing contract.",
        checks=(Check("test_suite.failed", "==", 0),),
        merged_from=(
            "flow_exponent:R0-test-suite",
            "binder:R9-existing-suite",
            "ordered_layers:COMP-3-vocabulary-suite-hygiene (suite)",
        ),
        extended=True,
    ),
    Gate(
        id="R-edge-darkening",
        item="global",
        kind="regression",
        metric="Darkest row of the 6 rows inward from the top edge of a dried stroke, the edge found as the first row "
        "whose paint (columns 36-92) is at least 5% of the middle's, over the mean of rows 60-67 about the stroke's "
        "path (edge ratio); the same at the bottom edge (far edge ratio); and the strongest paint just inside the "
        "edges of a dried flat wash over its interior",
        scenario="Flat 14, water 1.0, stroke from (20,64) to (108,64) at 110 px/s, dried, for french ultramarine and "
        "quinacridone rose at 0.5, 1 and 4; the ordered study's flat wash (flat-12 rows of ultramarine 0.7)",
        comparator=">= / within / decreasing",
        threshold="Every edge ratio, at both edges, >= 1.15; ultramarine 1.0 within +/-15% of 0.8.0 (2.03); rose 1.0 "
        "within +/-50% (2.22); falling strictly with strength for each pigment; flat wash edge ratio >= 1.15",
        source="test_stroke_on_dry_paper_dries_darker_at_its_edge; Deegan 1997, Curtis 1997 (every edge of a wash "
        "drying on dry paper darkens); Gonzalez-Gutierrez et al. 2019 (deposits saturate at high concentration); "
        "engineering budgets around 0.8.0. 0.8.0's far edges: ultramarine 1.65/1.53/1.28, rose 1.70 at 1.0.",
        checks=(
            Check("edge_french_ultramarine_1.edge_ratio", ">=", 1.15),
            within("edge_french_ultramarine_1.edge_ratio", 0.85, 1.15),
            Check("edges.french_ultramarine", ">=", 1.15),
            Check("edges.quinacridone_rose", ">=", 1.15),
            Check("edges.french_ultramarine_far", ">=", 1.15),
            Check("edges.quinacridone_rose_far", ">=", 1.15),
            Check("edges.french_ultramarine", "decreasing"),
            Check("edges.quinacridone_rose", "decreasing"),
            within("edge_quinacridone_rose_1.edge_ratio", 0.5, 1.5),
            Check("flat_wash_flat.edge_ratio", ">=", 1.15),
        ),
        merged_from=(
            "flow_exponent:R1-edge-darkening",
            "binder:R1-edge-darkening-present",
            "binder:R2-edge-contrast-falls-with-strength",
            "binder:R3-edge-look-band",
            "ordered_layers:REG-5-flat-wash (edge)",
        ),
        correction="The reviewed metric, carried from the test, took the darkest of rows 48-53 whatever the stroke "
        "did: on 0.8.0 the stroke's paint begins at row 50 and its rim lies at row 51, so a flow that spread the "
        "stroke three rows further would leave the rim outside the band and read as a loss of edge darkening. The "
        "edge is now found from the paint, which gives the same values on 0.8.0, and the bottom edge is held to the "
        "same floor.",
    ),
    Gate(
        id="R-stroke-width",
        item="global",
        kind="regression",
        metric="Rows touched by pigment in the dried edge-darkening stroke (ultramarine 1.0)",
        scenario="As R-edge-darkening",
        comparator="abs difference <=",
        threshold="1 row from 0.8.0 (30)",
        source="0.8.0's own value.",
        checks=(Check("edge_french_ultramarine_1.painted_rows", "near", 1),),
        merged_from=("flow_exponent:R2-stroke-width",),
    ),
    Gate(
        id="R-flat-wash-evenness",
        item="global",
        kind="regression",
        metric="Coefficient of variation of a dried flat wash: of 8x8 box means (mop wash), of 9x9 block means "
        "(round-12 rows), and of the pixels (flat-12 rows)",
        scenario="Three mop-16 strokes of ultramarine 0.6 at y 40, 64, 88 over [44:84, 36:92]; round 12, ultramarine "
        "0.7, rows every 13.2 px reloaded every third, over [36:90, 36:90]; flat 12, ultramarine 0.7, rows every "
        "13 px from y 26, over [40:90, 40:90]",
        comparator="<=",
        threshold="1.25 x 0.8.0 (0.0752 and 0.0833); 0.16",
        source="0.8.0's own values with a 25% engineering budget; the ordered study's 0.8.0 value 0.1407.",
        checks=(
            Check("flat_wash_mop.box_variation", "<=", 1.25, "baseline"),
            Check("flat_wash_round.block_variation", "<=", 1.25, "baseline"),
            Check("flat_wash_flat.interior_variation", "<=", 0.16),
        ),
        merged_from=(
            "flow_exponent:R3-flat-wash-evenness",
            "binder:R6-flat-wash-evenness",
            "ordered_layers:REG-5-flat-wash (evenness)",
        ),
    ),
    Gate(
        id="R-drying-time",
        item="global",
        kind="regression",
        metric="Seconds returned by Studio.dry(), and simulated seconds with standing water for the mop wash",
        scenario="The edge stroke (ultramarine 1.0); the mop wash; the mop wash watched in 1 s steps; the binder's "
        "patch of three flat-12 strokes of ultramarine 1.0; the ordered study's flat wash",
        comparator="within",
        threshold="+/-15% of 0.8.0 (192 s, 280 s, 88 s, 216 s); +/-10% for the flat wash (232 s)",
        source="0.8.0's own values plus engineering budgets; Jackson's 2021 (added gum slows drying only by minutes).",
        checks=(
            within("edge_french_ultramarine_1.drying_seconds", 0.85, 1.15),
            within("flat_wash_mop.drying_seconds", 0.85, 1.15),
            within("wet_phase.seconds_with_film", 0.85, 1.15),
            within("patch_drying.drying_seconds", 0.85, 1.15),
            within("flat_wash_flat.drying_seconds", 0.9, 1.1),
        ),
        merged_from=(
            "flow_exponent:R4-drying-and-wet-phase",
            "binder:R8-drying-time",
            "ordered_layers:REG-5-flat-wash (drying)",
        ),
    ),
    Gate(
        id="R-bloom",
        item="global",
        kind="regression",
        metric="Deposit at the centre of a bloom and on its rim against the surrounding wash",
        scenario="Clear water dropped into a wash at film 0.03, dried: the mop wash with a round-8 dab held 0.6 s "
        "(centre r<4 and highest 2 px ring within 30 px, over r 24-30); five round-12 rows of ultramarine 1.0 "
        "(peak of the 1 px radial profile over its inner 4 px); round-12 rows of burnt umber 0.6 on paper seeds 3-7 "
        "(median over the papers of the r<4 disc and of the highest 2 px ring, each over r 26-30)",
        comparator="<= / >= / within",
        threshold="Mop: centre <= 0.8 and rim >= 1.1, each within +/-15% of 0.8.0 (0.603, 1.190); round: peak "
        "over inside >= 0.8 x 0.8.0 (1.945); umber: median centre <= 0.8 and median rim >= 1.15, each within "
        "+/-15% of 0.8.0",
        source="Curtis 1997 backrun; 0.8.0's own values plus engineering budgets. The umber centre was a 2 px ring "
        "on one paper, bounded at 0.95; on 0.8.0 that ring reads 0.59-0.91 across paper seeds 3-10, so it measured "
        "the grain under the dab as much as the bloom. It is now the r<4 disc used for the mop bloom (0.69-0.76 "
        "across the same papers), as a median over five papers, with the mop bloom's bounds.",
        checks=(
            Check("bloom_mop.centre_over_wash", "<=", 0.8),
            within("bloom_mop.centre_over_wash", 0.85, 1.15),
            Check("bloom_mop.rim_over_wash", ">=", 1.1),
            within("bloom_mop.rim_over_wash", 0.85, 1.15),
            Check("bloom_round.peak_over_inside", ">=", 0.8, "baseline"),
            Check("umber_bloom_seeds.centre_median", "<=", 0.8),
            within("umber_bloom_seeds.centre_median", 0.85, 1.15),
            Check("umber_bloom_seeds.rim_median", ">=", 1.15),
            within("umber_bloom_seeds.rim_median", 0.85, 1.15),
        ),
        merged_from=("flow_exponent:R5-bloom", "binder:R4-bloom-forms", "ordered_layers:REG-6-bloom"),
    ),
    Gate(
        id="R-lifting",
        item="global",
        kind="regression",
        metric="Paint lifted: the line a drained brush draws through a wash losing its shine against the wash, and "
        "what the brush took; the share of non-staining paint lifted from dried strokes; the share lifted from a "
        "dried wash and the value gained",
        scenario="test_drained_brush_lifts_paint_from_a_wash_that_is_losing_its_shine; two dried flat-12 strokes "
        "of ultramarine and of cerulean at 0.25, 1 and 4, lifted by a damp flat 8 (three passes, wait 10 s, blot "
        "radius 10); a dried flat wash of ultramarine 1.2 lifted the same way and dried",
        comparator="< / > / within / >=",
        threshold="Line over wash < 0.8 and within +/-15% of 0.8.0 (0.746); taken > 5; non-staining shares within "
        "+/-3% of 0.8.0 (ultramarine 0.4152, 0.4166, 0.4174); dried wash lifted >= 0.40 with value gain >= 0.10",
        source="Existing test thresholds; Jackson's Art 2021 (non-staining paint lifts cleanly with or without gum); "
        "0.8.0's own values (0.478, 0.144) for the dried wash; engineering budgets.",
        checks=(
            Check("drained_lift.lifted_ratio", "<", 0.8),
            within("drained_lift.lifted_ratio", 0.85, 1.15),
            Check("drained_lift.taken", ">", 5.0),
            within("lifts.french_ultramarine", 0.97, 1.03),
            within("lifts.cerulean_blue", 0.97, 1.03),
            Check("dried_wash_lift.lifted_share", ">=", 0.40),
            Check("dried_wash_lift.value_gain", ">=", 0.10),
        ),
        merged_from=(
            "flow_exponent:R6-lifting",
            "binder:R5-lifting-works",
            "binder:R10-non-staining-lift-unchanged",
            "ordered_layers:REG-8-lifting",
        ),
    ),
    Gate(
        id="R-tilt-run",
        item="global",
        kind="regression",
        metric="Lowest wet row with a tilt of 0.2 minus with no tilt",
        scenario="test_loaded_passage_runs_down_a_tilted_sheet",
        comparator=">=",
        threshold="6 rows, and at least 0.75 x 0.8.0 (18, so 14 rows)",
        source="Existing test floor plus a 25% budget.",
        checks=(Check("tilt_run.run_rows", ">=", 6), Check("tilt_run.run_rows", ">=", 0.75, "baseline")),
        merged_from=("flow_exponent:R7-tilt-run",),
    ),
    Gate(
        id="R-wet-in-wet",
        item="global",
        kind="regression",
        metric="Spread of strong paint charged into wet paint: rms width of cadmium red across its stroke; "
        "second-moment radius of a rose dab; radii at which an ultramarine dab falls to a half and a tenth",
        scenario="Clear mop-16 wash; cadmium red 4.0 from a round 5 drained to 0.6, stroked at y 64 from x 34 to 94 "
        "at pressure 0.8 once the film reaches 0.5, 0.3 and 0.15 (wait_for_film), after fixed waits of 5, 20 and "
        "40 s, and on dry paper; rose 0.5, 2 and 6 dabbed into five clear mop strokes 10 s old; ultramarine 4.0 "
        "dabbed into four clear mop-12 strokes 2 s old; all dried",
        comparator=">= / within",
        threshold="Width at each film >= 1.5 x the dry width and at 0.5 >= 2 x; each film and each fixed wait within "
        "+/-20% of 0.8.0 (8.21/5.62/6.48; 13.43/10.53/6.82); rose radii within +/-20% (18.5, 19.8, 21.6); "
        "ultramarine half radius 18 +/- 2 px and tenth radius 29 +/- 3 px",
        source="Skill SKILL.md spread table ('0.5 and deeper: twice its width or more'; '0.15 to 0.5: about one and "
        "a half times'); the trials' fixed waits; 0.8.0's own values plus budgets.",
        checks=(
            Check("charges.widths_over_dry", ">=", 1.5),
            Check("charges.film_0.5_over_dry", ">=", 2.0),
            within("charges.widths", 0.8, 1.2),
            within("charges.waited_widths", 0.8, 1.2),
            within("charges.rose_radii", 0.8, 1.2),
            Check("wet_in_wet_dab.half_radius", "between", (16, 20)),
            Check("wet_in_wet_dab.tenth_radius", "between", (26, 32)),
        ),
        merged_from=(
            "flow_exponent:R8a-wet-in-wet-by-film",
            "flow_exponent:R8b-wet-in-wet-fixed-waits",
            "binder:R7-wet-in-wet-spread",
            "ordered_layers:REG-7-wet-in-wet",
        ),
    ),
    Gate(
        id="R-stability",
        item="global",
        kind="regression",
        metric="(a) deepest film over 15 s over the deepest laid; (b) deepest film from wash rows that barely touch, "
        "over 40 s; (c) checkerboard index; (d) deep water on damp paper: finite, relative water error, mean "
        "|discrete Laplacian| after 10 s",
        scenario="(a)-(c): test_a_drying_film_does_not_gather_into_drops, test_wash_rows_that_barely_touch_do_not_"
        "pile_into_deep_drops, test_thick_wet_paint_does_not_settle_into_a_checkerboard. (d): 128 px, saturation = "
        "capacity, film 0.6 with a 48x48 block at 2.0 plus 0.02 noise, no evaporation or absorption, 10 s",
        comparator="<= / < / < / finite, <=, <=",
        threshold="(a) <= 1.1; (b) < 2.0; (c) < 0.01; (d) finite, error <= 1e-6, Laplacian <= 1.25 x 0.8.0 (0.00517)",
        source="Existing test thresholds; (d) guards the explicit bound at the depth clamp.",
        checks=(
            Check("drying_film_growth.deepest_over_laid", "<=", 1.1),
            Check("rows_barely_touching.deepest_film", "<", 2.0),
            Check("thick_paint_checkerboard.checkerboard", "<", 0.01),
            Check("deep_water_on_damp_paper.finite", "==", True),
            Check("deep_water_on_damp_paper.water_error", "<=", 1e-6),
            Check("deep_water_on_damp_paper.roughness", "<=", 1.25, "baseline"),
        ),
        merged_from=("flow_exponent:R9-stability",),
    ),
    Gate(
        id="R-thin-film-on-damp-paper",
        item="global",
        kind="regression",
        metric="Checkerboard index and deepest film over deepest at the start, after 10 s; finite; water error",
        scenario="128 px, seed 3, saturation = capacity, uniform film 0.03 and 0.08 with +/-15% uniform noise "
        "(generator seed 2), no evaporation or absorption, Sheet.advance(10)",
        comparator="<=",
        threshold="Checkerboard and deepest ratio each <= 1.25 x 0.8.0 (0.0083 / 2.53 at 0.03; 0.0092 / 2.76 at "
        "0.08); finite; error <= 1e-6",
        source="The stiffest corner of the explicit scheme (wicking times the wetting pull).",
        checks=(
            Check("thin_film_on_damp_paper.checkerboard_0.03", "<=", 1.25, "baseline"),
            Check("thin_film_on_damp_paper.deepest_over_start_0.03", "<=", 1.25, "baseline"),
            Check("thin_film_on_damp_paper.checkerboard_0.08", "<=", 1.25, "baseline"),
            Check("thin_film_on_damp_paper.deepest_over_start_0.08", "<=", 1.25, "baseline"),
            Check("thin_film_on_damp_paper.finite_0.03", "==", True),
            Check("thin_film_on_damp_paper.finite_0.08", "==", True),
            Check("thin_film_on_damp_paper.water_error_0.03", "<=", 1e-6),
            Check("thin_film_on_damp_paper.water_error_0.08", "<=", 1e-6),
        ),
        merged_from=("flow_exponent:R9e-thin-film-on-damp-paper",),
    ),
    Gate(
        id="R-shine-timing",
        item="global",
        kind="regression",
        metric="Seconds for the film at (64,64) to thin to 0.3, 0.15 and 0.12 after laying",
        scenario="Three overlapping strokes of ultramarine 0.6 at y 40, 64, 88 with round 16 and, separately, mop 16; "
        "wait_for_film with 1 s looks",
        comparator="within",
        threshold="+/-15% of 0.8.0 at each film (round 34/50/53 s; mop 51/69/73 s)",
        source="Skill SKILL.md ('down to 0.12 in about a minute') and 0.8.0's own values.",
        checks=(
            within("shine_round.seconds_to_film", 0.85, 1.15),
            within("shine_mop.seconds_to_film", 0.85, 1.15),
        ),
        merged_from=("flow_exponent:R10-shine-timing",),
    ),
    Gate(
        id="R-staining-wet-balance",
        item="global",
        kind="regression",
        metric="Share of quinacridone rose still in suspension 20 s after a patch is laid",
        scenario="The binder's patch (three flat-12 strokes) of rose 1 and 4, wait 20 s",
        comparator="within",
        threshold="+/-5% of 0.8.0 (0.7955 and 0.7180)",
        source="0.8.0's own values; protects the tuned settling balance.",
        checks=(
            within("wet_balance_1.suspended_share", 0.95, 1.05),
            within("wet_balance_4.suspended_share", 0.95, 1.05),
        ),
        merged_from=("binder:R11-staining-wet-balance",),
    ),
    Gate(
        id="R-glaze-over-dried-paint",
        item="global",
        kind="regression",
        metric="CV of 6x6 block means of glaze blue over a dried rose patch [50:78, 40:88], and mean blue over the "
        "patch over mean blue over clean paper [24:42, 30:90]",
        scenario="Rose 2.0 patch, dried; ultramarine 0.7 in round-12 rows every 13.2 px across the sheet, reloaded "
        "every third row; dried",
        comparator="<= / within",
        threshold="CV <= 1.25 x 0.8.0 (0.0564); ratio within +/-10% of 0.8.0 (1.124)",
        source="0.8.0's own values with engineering budgets; protects glazing, the main layering technique.",
        checks=(
            Check("glaze_over_rose.variation_over_patch", "<=", 1.25, "baseline"),
            within("glaze_over_rose.patch_over_paper", 0.9, 1.1),
        ),
        merged_from=("binder:R12-glaze-over-dried-paint",),
    ),
    Gate(
        id="R-glaze-disturbance",
        item="global",
        kind="regression",
        metric="Share of a dried rose patch's pigment moved out of place by one clear-water glaze",
        scenario="Rose patch at 0.5 and 2.0, dried; three clear mop-16 strokes across it; dried",
        comparator="within",
        threshold="+/-25% of 0.8.0 (0.029 and 0.026)",
        source="0.8.0's own values with an engineering budget.",
        checks=(
            within("glaze_disturbance_0.5.moved_share", 0.75, 1.25),
            within("glaze_disturbance_2.moved_share", 0.75, 1.25),
        ),
        merged_from=("binder:R13-glaze-disturbance",),
    ),
    Gate(
        id="R-later-layer-does-not-unstain",
        item="global",
        kind="regression",
        metric="Share of dried rose 1.0 lifted under a dried ultramarine 2.0 glaze over the share lifted with no glaze",
        scenario="Two flat-12 strokes of rose 1.0, dried; two of ultramarine 2.0 over them, dried; the binder lift",
        comparator="within",
        threshold="+/-15% of 0.8.0 (0.9975)",
        source="handprint pigmt3 (stain is particles lodged among the fibres, beyond the reach of gum laid later).",
        checks=(within("lift_ratios.under_glaze_over_alone", 0.85, 1.15),),
        merged_from=("binder:R14-later-layer-does-not-unstain",),
    ),
    Gate(
        id="R-single-paint-picture",
        item="global",
        kind="regression",
        metric="Largest absolute difference of the value view from 0.8.0's picture of the same sheet",
        scenario="One paint each: the ordered study's flat wash, umber bloom, dried-wash lift and wet-in-wet dab",
        comparator="<=",
        threshold="1e-4",
        source="Kubelka-Munk: layers of the same make-up composite as their sum; well under 1/255.",
        checks=(
            Check("flat_wash_flat.picture_difference", "<=", 1e-4),
            Check("bloom_umber.picture_difference", "<=", 1e-4),
            Check("dried_wash_lift.picture_difference", "<=", 1e-4),
            Check("wet_in_wet_dab.picture_difference", "<=", 1e-4),
        ),
        merged_from=("ordered_layers:REG-2-single-paint-picture",),
    ),
    Gate(
        id="R-unset-paint-mixes",
        item="global",
        kind="regression",
        metric="Where a second paint is laid before the first has set: the largest amount in any paint layer, and "
        "the largest difference of the value view from 0.8.0's picture",
        scenario="Burnt umber 3.0 dabbed into the shining mop wash of ultramarine 0.6, and again once the film has "
        "gone at the second spot with the paper above damp_threshold; dried",
        comparator="<=",
        threshold="Layer fields 0 in those cells; value within 1e-4 of 0.8.0; the second charge lands unset",
        source="Wet-in-wet, charging and backruns mix and must not layer.",
        checks=(
            Check("unset_mixing.second_charge_unset", "==", True),
            Check("unset_mixing.layered_paint", "<=", 0.0),
            Check("unset_mixing.picture_difference", "<=", 1e-4),
        ),
        merged_from=("ordered_layers:REG-3-unset-paint-mixes",),
    ),
    Gate(
        id="R-transparent-paint-commutes",
        item="global",
        kind="regression",
        metric="The part of |V(paint over dried burnt umber) - V(burnt umber over dried paint)| for transparent "
        "paints that the picture adds to 0.8.0's picture of the same sheets: |A - A_0.8.0|",
        scenario="Columns of phthalo green, ultramarine and quinacridone rose 3.0 laid over a dried umber 2.0 band, "
        "and the band laid over the dried columns",
        comparator="<=",
        threshold="0.03",
        source="Kubelka-Munk as S -> 0: transmittances multiply and the order commutes. 0.8.0 noise is up to 0.014.",
        checks=(Check("commute.optical_differences", "<=", 0.03),),
        merged_from=("ordered_layers:REG-4-transparent-commute",),
        correction="The reviewed metric, the raw asymmetry, is 0.017, 0.039 and 0.014 on 0.8.0 for phthalo, "
        "ultramarine and rose, so ultramarine fails on the rig it protects. 0.8.0 pictures every sheet as one summed "
        "layer, so that asymmetry is all physics: ultramarine settles differently on dried umber than on bare paper "
        "(Kubelka-Munk composition of the same deposits differs by 0.045). The law cited is optical, so the gate "
        "now measures the asymmetry the picture adds to 0.8.0's picture of the same sheets; the raw asymmetry is "
        "still recorded (commute.differences).",
    ),
    Gate(
        id="R-technique-trials",
        item="global",
        kind="regression",
        metric="Trials of trials/engine_trials.py that fail to paint; for trials glazed only with transparent paint, "
        "the mean CIEDE2000 difference of the colour view from 0.8.0's picture of the same sheet",
        scenario="trials/engine_trials.py (all trials, about 30 minutes on the GPU); the glaze trial",
        comparator="== / <=",
        threshold="None fails; mean dE00 <= 1.0",
        source="Protects ordinary watercolour. A dE00 of about 1 is a just-noticeable difference (CIE).",
        checks=(
            Check("technique_trials.failed_trials", "==", ()),
            Check("technique_trials.transparent_glaze_difference", "<=", 1.0),
        ),
        merged_from=("ordered_layers:REG-9-technique-trials",),
        extended=True,
        correction="engine_trials.py records no pass criteria, so 'within its current pass criterion' is taken as "
        "'paints without error'; the transparent glazing passage is the glaze trial (ultramarine over dried hansa "
        "yellow), compared with 0.8.0's renderer on the same sheet.",
    ),
    # ------------------------------------------------------------------------------------------ film mobility exponent
    Gate(
        id="G1-levelling-exponent",
        item="flow_exponent",
        kind="physical",
        metric="Slope of ln(decay rate) against ln(H) for a ripple at pool scale, and every local slope between "
        "neighbouring depths",
        scenario="Two 64x128 sheets (paper seed 3) per depth, batched. Evaporation, absorption and paper evaporation "
        "0. Uniform film H in {0.2, 0.45, 0.9}; one sheet carries a 5% cosine ripple in mode 8 across x "
        "(wavelength 32 px). Amplitude = projection of the difference onto the mode over rows 24-40 and columns "
        "24-104. Rate = least-squares slope of ln(amplitude) in 0.2 s steps until ln has fallen by 0.15 (at most "
        "60 s). Valid only on dry paper at wavelengths of 32 px or more.",
        comparator="within",
        threshold="[2.75, 3.25] for the overall slope and for each local slope",
        source="Orchard (1962) long-wave levelling, rate proportional to h^3 for a no-slip film (Arscott 2020; "
        "Saxena et al. 2021). Tolerance: half of the half-gap to the h^2 law. Measured: 0.8.0 2.001; h3f 2.988.",
        checks=(
            Check("levelling_rates.exponent", "between", (2.75, 3.25)),
            Check("levelling_rates.local_exponents", "between", (2.75, 3.25)),
        ),
        expected_on_baseline="fail",
    ),
    Gate(
        id="G2-slope-run-time-exponent",
        item="flow_exponent",
        kind="physical",
        metric="alpha = 1/n, where n minimises the relative residual of a linear fit x_N(t)^n = a + K t over n in "
        "[1.5, 7]; x_N is the distance of the front from the top of the band, the lowest row where the excess "
        "depth over columns 8-24 exceeds 0.1, interpolated",
        scenario="Sheet 320 x 32, dry paper (seed 3), evaporation, absorption and paper evaporation 0, standing "
        "film 0.02; a band in rows 16-32 1.0 deep across the full width; tilt (0, 0.2); t = 8, 16, 32, 64, 96 s",
        comparator="within",
        threshold="[0.292, 0.375] (1/3 +/- 1/24)",
        source="Huppert (1982, Nature 300, 427): x_N proportional to t^(1/3) for a viscous current on a slope; the "
        "h^2 law gives t^(1/2). Measured: 0.8.0 0.513; h3f 0.347.",
        checks=(Check("slope_runs.time_exponent", "between", (0.292, 0.375)),),
        expected_on_baseline="fail",
    ),
    Gate(
        id="G3-slope-run-volume-exponent",
        item="flow_exponent",
        kind="physical",
        metric="ln(K_A / K_A/2) / (n ln 2), K the fitted rate of x_N^n = a + K t (n from G2) for a band of "
        "cross-section A and one of A/2",
        scenario="As G2, with a second sheet whose band is rows 16-24 (A/2)",
        comparator=">=",
        threshold="0.583 (7/12, midway between the h^2 law's 1/2 and the h^3 law's 2/3)",
        source="Huppert 1982b: x_N proportional to A^(2/3) for h^3 and A^(1/2) for h^2. Measured: 0.8.0 0.515; "
        "h3f 0.716 (overshoot reported, not used as a pass of the asymptote).",
        checks=(Check("slope_runs.volume_exponent", ">=", 0.583),),
        expected_on_baseline="fail",
    ),
    Gate(
        id="R-cal-full-wash-calibration",
        item="flow_exponent",
        kind="regression",
        metric="Levelling rate of the G1 scenario at H = 1.0, and at H = 1.3 (where the mobility is capped), over 0.8.0",
        scenario="G1 scenario at depths 1.0 and 1.3",
        comparator="within",
        threshold="[0.95, 1.05] at both depths",
        source="A full wash is the engine's unit; its rates were set by eye at that depth. The change must alter the "
        "depth law, not the calibration or the peak the stability margin rests on.",
        checks=(
            within("levelling_rates.rate_full_wash", 0.95, 1.05),
            within("levelling_rates.rate_mobility_limit", 0.95, 1.05),
        ),
    ),
    Gate(
        id="P1-wet-cost",
        item="flow_exponent",
        kind="performance",
        metric="Wall time per simulated second of wet advance over 0.8.0",
        scenario="benchmark.py, 770x540 sheet, 6 pigments, a wash with strong colour charged in, median of repeats",
        comparator="<=",
        threshold="1.10",
        source="Engineering budget (noise allowance). The arithmetic per face is unchanged except for one clamp.",
        checks=(Check("benchmark.wet_seconds_per_second", "<=", 1.10, "baseline"),),
        correction="Measured on the binding 770x540 sheet against the recorded baseline, not interleaved at 256 px.",
    ),
    Gate(
        id="P2-whole-wash-cost",
        item="flow_exponent",
        kind="performance",
        metric="Wall time of Studio.dry() from the same laid 256 px wash, over 0.8.0",
        scenario="benchmark.py: 256 px, 3 pigments, the wash of the wet-cost scenario laid once and dried from that "
        "state, median of 3",
        comparator="<=",
        threshold="1.10",
        source="Captures the longer wet phase (+6% simulated wet seconds for h3f).",
        checks=(Check("benchmark.wash_drying_seconds", "<=", 1.10, "baseline"),),
    ),
    Gate(
        id="P3-memory-checkpoint",
        item="flow_exponent",
        kind="performance",
        metric="Per-sheet tensor bytes and torch.save size of Sheet.state(), leaving out the fields the binder (gum) "
        "and the ordered layers (underlying, lowest, _set) add",
        scenario="256 px sheet with 3 pigments (cadmium red, ultramarine, burnt umber)",
        comparator="==",
        threshold="Equal to 0.8.0 (5,242,916 and 3,673,037 bytes)",
        source="No new state.",
        checks=(
            Check("benchmark.sheet_bytes_256_3_kept", "near", 0),
            Check("benchmark.state_bytes_256_3_kept", "near", 0),
        ),
        correction="Measured over the sheet in all, the flow item's 'no new state' fails as soon as the binder or "
        "the layers add their approved fields in the same pull request. Each item's memory gate now counts every "
        "field but those the other items add (X3, X4, PERF-5 likewise).",
    ),
    Gate(
        id="P4-added-test-time",
        item="flow_exponent",
        kind="performance",
        metric="Wall time of the scenarios behind the new tests: G1, the G2/G3 slope batch and R9e",
        scenario="benchmark.py runs levelling_rates, slope_runs and thin_film_on_damp_paper one after another, alone",
        comparator="<=",
        threshold="120 s in total",
        source="Engineering budget: the suite takes about 3 min on the GPU.",
        checks=(Check("benchmark.new_test_seconds", "<=", 120.0),),
    ),
    # ------------------------------------------------------------------------------------------ gum arabic binder
    Gate(
        id="P1-gum-viscosity-matches-data",
        item="binder",
        kind="physical",
        metric="Effective relative viscosity r(0)/r(c), r the decay rate of an imposed cosine ripple measured by "
        "projection onto it over 0.3 s in [48:80, 40:88]",
        scenario="128 px, seed 3, evaporation, absorption, paper evaporation and Marangoni off. Film d(1 + 0.15 cos "
        "2 pi x / lambda) on dry paper in [32:96, 32:96], gum = c x water. d in {0.3, 0.6}, lambda in {16, 32} px, "
        "c in {0, 0.05, 0.10, 0.20}; Sheet.advance(0.3)",
        comparator="between",
        threshold="In every (d, lambda): 3.0-6.7 at c = 0.05, 6.7-13.5 at 0.10, 33-74 at 0.20; max/min across the "
        "four cases <= 1.2 at each c",
        source="Agri-Spray Acacia RE table at 25 C (4, 10, 44 cP over water at 0.89 mPa s); Kersten et al. 2025 "
        "(twofold band at 10%); thin-film Stokes flow, where viscosity divides every flux.",
        checks=(
            Check("gum_levelling.viscosity_0.05", "between", (3.0, 6.7)),
            Check("gum_levelling.viscosity_0.1", "between", (6.7, 13.5)),
            Check("gum_levelling.viscosity_0.2", "between", (33.0, 74.0)),
            Check("gum_levelling.viscosity_spread_0.05", "<=", 1.2),
            Check("gum_levelling.viscosity_spread_0.1", "<=", 1.2),
            Check("gum_levelling.viscosity_spread_0.2", "<=", 1.2),
        ),
        expected_on_baseline="fail",
    ),
    Gate(
        id="P2-lift-rises-with-strength-staining",
        item="binder",
        kind="physical",
        metric="Share of the pigment under the lifting path removed from the sheet, for quinacridone rose "
        "(staining 6) and phthalo green (staining 8) at strengths 0.25, 1 and 4; the rise at each step",
        scenario="Two flat-12 strokes at y 56 and 72, dried; flat 8, water 0.8, three passes along y = 64 at "
        "80 px/s; wait 10 s; blot radius 10",
        comparator="strictly increasing",
        threshold="Each step up in strength raises the share by >= 1% relative, for both pigments",
        source="handprint pigmt3 (gum coating holds pigment above the fibres); AIC Paper Conservation Catalog 1985. "
        "Step: twenty times the 0.8.0 rig's spread across strength (0.05%).",
        checks=(
            Check("lift_ratios.quinacridone_rose_steps", ">=", 0.01),
            Check("lift_ratios.phthalo_green_steps", ">=", 0.01),
        ),
        expected_on_baseline="fail",
    ),
    Gate(
        id="P3-damp-paper-lifts-more",
        item="binder",
        kind="physical",
        metric="Share of rose lifted once the film has just gone (paper >= 0.5 full), over the share lifted after "
        "Studio.dry()",
        scenario="Two flat-12 strokes of rose 1.0 at y 56 and 72; wait in 2 s steps until no film remains; the "
        "binder lift; against the same lift after dry()",
        comparator=">",
        threshold="1.0 (with the paper at least half full at the damp lift)",
        source="Practitioner consensus (Washes & Wells 2026; Still Lifes Matter 2017; Lee Muir-Haman 2019): gum in "
        "damp paper has not set. 0.8.0 0.73.",
        checks=(
            Check("lift_ratios.damp_over_dry", ">", 1.0),
            Check("damp_lift.paper_fullness", ">=", 0.5),
        ),
        expected_on_baseline="fail",
    ),
    Gate(
        id="P4-coffee-ring-weakens-with-gum",
        item="binder",
        kind="physical",
        metric="Edge ratio of the dried edge stroke (rim sought inward from the edge found in the paint, as in "
        "R-edge-darkening) with its gum multiplied by k in {0, 1, 3} at once after the stroke",
        scenario="Flat 14, french ultramarine 1.0, water 1.0, stroke from (20,64) to (108,64) at 110 px/s; Sheet.gum "
        "multiplied by k; dried",
        comparator="strictly decreasing in k",
        threshold="edge(k=0) > edge(k=1) > edge(k=3)",
        source="Cui et al. 2012 (dissolved polymer viscosity weakens the ring); Gonzalez-Gutierrez et al. 2019.",
        checks=(Check("edges.gum_scaled", "decreasing"),),
        expected_on_baseline="fail",
    ),
    Gate(
        id="I1-gum-conserved-in-advance",
        item="binder",
        kind="physical",
        metric="|sum(gum) after - before| / before",
        scenario="Sheet.advance(20) after three round-10 strokes of rose 3.0; studio.wait(5) with evaporation and "
        "absorption off after three mop strokes of ultramarine 4.0",
        comparator="<=",
        threshold="1e-5",
        source="Conservation: gum neither evaporates nor settles; float32 summation margin.",
        checks=(
            Check("gum_bookkeeping.advance_change", "<=", 1e-5),
            Check("gum_bookkeeping.wait_change", "<=", 1e-5),
        ),
        expected_on_baseline="fail",
        correction="Reviewed as an invariant expected to fail on 0.8.0, which keeps no gum; a gate that must fail "
        "until the item is built is a gate for new behaviour, so it is classed with the physical gates.",
    ),
    Gate(
        id="I3-gum-laid-with-pigment",
        item="binder",
        kind="physical",
        metric="sum(gum) / (GUM_PER_STRENGTH x sum(suspended + deposited)) after one stroke of rose 2 plus "
        "ultramarine 1 on dry paper",
        scenario="Round 10, one stroke from (24,64) to (104,64)",
        comparator="between",
        threshold="0.9 to 1.1",
        source="Design rule; the tip carries pigment without its gum (prototype 1.054).",
        checks=(Check("gum_bookkeeping.laid_over_pigment", "between", (0.9, 1.1)),),
        expected_on_baseline="fail",
        correction="Reclassed from invariant to physical for the reason given for I1.",
    ),
    Gate(
        id="I7-gum-conserved-through-masking-fluid",
        item="binder",
        kind="physical",
        metric="|sum(gum) after - before| / before across apply_mask, a wash over the mask, and remove_mask",
        scenario="A dried rose 2.0 patch; masking fluid across it; a clear mop wash over it; wait 5 s with "
        "evaporation and absorption off; the mask removed",
        comparator="<=",
        threshold="1e-5",
        source="Conservation: gum stays in the paper under the seal and nothing removes it.",
        checks=(Check("gum_bookkeeping.mask_change", "<=", 1e-5),),
        expected_on_baseline="fail",
        correction="Reclassed from invariant to physical for the reason given for I1.",
    ),
    Gate(
        id="R0-non-staining-paint-unchanged",
        item="binder",
        kind="regression",
        metric="Largest relative difference over every state field but gum between 0.8.0 and the engine",
        scenario="On the CPU, both engines in one process: the pool and dab of tests/test_together.py at 96 px with "
        "french ultramarine, and with cerulean blue, each followed by a drained-brush lift and dry()",
        comparator="<=",
        threshold="1e-6",
        source="Design: gum changes only staining paints in stage 1; Jackson's Art 2021.",
        checks=(Check("non_staining_unchanged.largest_relative_difference", "<=", 1e-6),),
    ),
    Gate(
        id="C1-old-state-loads-and-rebuilds-gum",
        item="binder",
        kind="compatibility",
        metric="load_state of a state without 'gum' succeeds; gum equals GUM_PER_STRENGTH x sum(suspended + "
        "deposited) to 1e-6 relative; a further stroke and wait leave every field finite",
        scenario="A 96 px rose pool and dab saved without gum, loaded into a fresh sheet, then a stroke and a 3 s wait",
        comparator="==",
        threshold="true (an engine that keeps no gum has none to rebuild)",
        source="Compatibility requirement: a continued 0.8.0 painting follows one rule.",
        checks=(
            Check("old_state_loads.gum_rebuilt", "==", True),
            Check("old_state_loads.continues_finite", "==", True),
        ),
    ),
    Gate(
        id="X1-wet-cost",
        item="binder",
        kind="performance",
        metric="Wall time per simulated second, wet phase, over 0.8.0; valid only with the dry-phase control within "
        "0.95-1.05",
        scenario="benchmark.py, 770x540, 6 pigments",
        comparator="<=",
        threshold="1.25",
        source="Stated engineering budget.",
        checks=(
            Check("benchmark.wet_seconds_per_second", "<=", 1.25, "baseline"),
            within("benchmark.dry_seconds_per_second", 0.95, 1.05),
        ),
        correction="Measured by benchmark.py on the binding 770x540 sheet against the baseline recorded alone on 0.8.0, not with both engines interleaved in one process at 256 px; the dry-phase control is the same run's X2 measurement.",
    ),
    Gate(
        id="X2-dry-cost",
        item="binder",
        kind="performance",
        metric="Wall time per simulated second, dry phase (film removed, paper damp), over 0.8.0",
        scenario="benchmark.py, 770x540, 6 pigments",
        comparator="<=",
        threshold="1.05",
        source="That code path is untouched, so any larger ratio is a defect or a measurement fault.",
        checks=(Check("benchmark.dry_seconds_per_second", "<=", 1.05, "baseline"),),
        correction="Measured by benchmark.py on the binding 770x540 sheet against the baseline recorded alone on 0.8.0, not with both engines interleaved in one process at 256 px; the film is removed and the paper set to 0.8 of its capacity, as asked.",
    ),
    Gate(
        id="X3-memory",
        item="binder",
        kind="performance",
        metric="Tensor bytes added per sheet, leaving out the ordered layers' fields, and peak transient allocation "
        "during a wet advance, over 0.8.0",
        scenario="benchmark.py: the tensors of a 770x540 sheet with 6 pigments; the peak by "
        "torch.cuda.max_memory_allocated during a wet advance",
        comparator="<=",
        threshold="4*H*W + 1024 bytes added; peak <= 1.10 x baseline",
        source="Stated engineering budget (one float32 field).",
        checks=(
            Check("benchmark.sheet_bytes_770_6_without_layers", "<=", 4 * 540 * 770 + 1024, "baseline_plus"),
            Check("benchmark.peak_wet_bytes", "<=", 1.10, "baseline"),
        ),
        correction="The bytes added are counted leaving out the ordered layers' fields (underlying, lowest, _set), "
        "which would otherwise exceed this allowance in the one pull request; peak transient memory is the whole "
        "engine's.",
    ),
    Gate(
        id="X4-checkpoint-size",
        item="binder",
        kind="performance",
        metric="state.pt bytes, engine minus 0.8.0, for the same 64 px painting, leaving out the ordered layers' fields",
        scenario="Session.create at 64 px, two strokes, a wait",
        comparator="<=",
        threshold="4*H*W + 1024 bytes per sheet",
        source="Stated engineering budget.",
        checks=(Check("benchmark.session_state_bytes_without_layers", "<=", 4 * 64 * 64 + 1024, "baseline_plus"),),
        correction="The saved state is counted leaving out the ordered layers' fields, for the reason given on X3.",
    ),
    Gate(
        id="X5-stroke-cost",
        item="binder",
        kind="performance",
        metric="Wall time per Studio.stroke over 0.8.0",
        scenario="256 px, four round-10 strokes of rose 2.0 and one clear flat-8 lifting stroke, median of repeats",
        comparator="<=",
        threshold="1.15",
        source="Stated engineering budget.",
        checks=(Check("benchmark.stroke_seconds", "<=", 1.15, "baseline"),),
        correction="Median of the benchmark's repeats against the recorded baseline, not ABBA rounds in one process.",
    ),
    Gate(
        id="X6-cpu-wet-cost",
        item="binder",
        kind="performance",
        metric="Wall time per simulated second, wet phase, on the CPU, over 0.8.0",
        scenario="128x128 on the CPU, median of repeats",
        comparator="<=",
        threshold="1.25",
        source="Stated engineering budget; tests and machines without a GPU run the engine on the CPU.",
        checks=(Check("benchmark.cpu_wet_seconds_per_second", "<=", 1.25, "baseline"),),
        correction="Median of the benchmark's repeats against the recorded baseline, not ABBA rounds in one process.",
    ),
    # ------------------------------------------------------------------------------------------ ordered layers
    Gate(
        id="PHY-1-layering-fraction",
        item="ordered_layers",
        kind="physical",
        metric="f = (C_sim - C_sum)/(C_lay - C_sum) for each column and coat; C = value of the white over the band "
        "over the same white over paper; in C_lay the paint beneath is min(deposit before the coat, deposit after) "
        "per pigment, from snapshots; in C_sum all paint is one layer (0.8.0's renderer)",
        scenario="white_coats, 128 px: band of umber 2 + ultramarine 1, dried; opaque white 1.5/3/4.5/8 in round-5 "
        "columns; coat 1 dried, then coat 2 dried; 8 points",
        comparator=">=",
        threshold="0.75 at every column and coat",
        source="Kubelka 1954 composition law; Curtis 1997 section 5. Measured: 0.8.0 0.00-0.01; prototype 0.81-0.91.",
        checks=(Check("white_coats.layering_fraction", ">=", 0.75),),
        expected_on_baseline="fail",
    ),
    Gate(
        id="PHY-2-ground-insensitivity",
        item="ordered_layers",
        kind="physical",
        metric="(slope of the value of two coats of white 4.5 against the value of the band, across 4 bands) / "
        "(the same slope for the summed Kubelka-Munk picture of the run's deposits)",
        scenario="under_darkness, 128 px: bands of umber+ultramarine at 0.75/1.5/3/6, two white columns, dried "
        "between coats",
        comparator="<=",
        threshold="0.6",
        source="Kubelka-Munk dR/dRg = T1^2/(1 - R1 Rg)^2 for a layer over a ground. Measured: 0.8.0 1.0; "
        "prototype 0.40.",
        checks=(Check("under_darkness.slope_ratio", "<=", 0.6),),
        expected_on_baseline="fail",
    ),
    Gate(
        id="PHY-3-order-follows-scattering",
        item="ordered_layers",
        kind="physical",
        metric="A_sim(paint) = V(paint 3.0 over a dried umber 2.0 band) - V(umber over the dried paint), against "
        "A_KM composed from each run's deposits with snapshot attribution",
        scenario="order_on_top and order_beneath, 128 px: phthalo green, yellow ochre, cadmium red, opaque white",
        comparator=">=",
        threshold="A_sim(opaque white) >= max(0.10, 0.5 x A_KM(opaque white)); sign(A_sim) = sign(A_KM) for every "
        "paint with |A_KM| >= 0.03",
        source="Kubelka 1954: order matters in proportion to the scattering of the upper layer. Measured: 0.8.0 "
        "0.026, prototype 0.287 (A_KM about 0.446).",
        checks=(
            Check("order.white_margin", ">=", 0.0),
            Check("order.signs_agree", "==", True),
        ),
        expected_on_baseline="fail",
    ),
    Gate(
        id="PHY-4-glaze-over-white",
        item="ordered_layers",
        kind="physical",
        metric="CIE C* of a phthalo green 0.8 glaze over dried opaque white 4.5 over C* of the same glaze over bare "
        "paper, per column",
        scenario="glaze_over_white, 128 px: white band dried, four glaze columns dried",
        comparator=">=",
        threshold="0.85 at every column",
        source="Johnston-Feller 2001, ch. 4. Measured: prototype 0.96-1.01; summed render (0.8.0) 0.71-0.74.",
        checks=(Check("glaze_over_white.chroma_ratio", ">=", 0.85),),
        expected_on_baseline="fail",
    ),
    Gate(
        id="PHY-5-set-transition",
        item="ordered_layers",
        kind="physical",
        metric="Share of the dark beneath the white in each column, and value over the band, against the moment the "
        "white was laid",
        scenario="set_time, 128 px. White 4.5 laid across a fresh dark band: while shiny; after the film has gone "
        "with the paper still fuller than damp_threshold; at the first look when the column reads dry; and 300 s "
        "later. Then dry.",
        comparator="<= / >= / monotone",
        threshold="Columns laid before the paint set: share <= 0.05 and value within 1e-4 of the summed picture. "
        "Columns laid after: share >= 0.9. Value non-decreasing across the transition.",
        source="Painting practice and gum softness (handprint; AIC); the set criterion is the engine's own dry stage.",
        checks=(
            Check("set_time.damp_moment_reached", "==", True),
            Check("set_time.unset_share_largest", "<=", 0.05),
            Check("set_time.unset_picture_error_largest", "<=", 1e-4),
            Check("set_time.set_share_least", ">=", 0.9),
            Check("set_time.over_band", "nondecreasing"),
        ),
        expected_on_baseline="fail",
        correction="The review laid the columns after fixed waits (5, 60, 60 and 400 s); here the moments are found "
        "by the readings the gate names, in 1 s looks, and each column is classed set or unset by its reading. "
        "Added in audit: the second column must land in the damp moment it is meant to test (film gone, paper "
        "still above damp_threshold; 0.8.0 reads 0.613 against 0.6), since a column classed set there would leave "
        "the gate passing without testing that moment.",
    ),
    Gate(
        id="PHY-6-fine-white-line",
        item="ordered_layers",
        kind="physical",
        metric="Peak value across a fine white line, averaged along the band",
        scenario="fine_line, 128 px: dark band dried; rigger 1.3, opaque white 4.5; one coat on one line, two on "
        "another, dried between",
        comparator=">=",
        threshold="two coats >= 0.60 and one coat >= 0.50",
        source="The documented symptom (SKILL.md line 225). Measured: 0.8.0 0.386/0.475; prototype 0.544/0.685.",
        checks=(
            Check("fine_line.two_coats_peak", ">=", 0.60),
            Check("fine_line.one_coat_peak", ">=", 0.50),
        ),
        expected_on_baseline="fail",
    ),
    Gate(
        id="PHY-7-layers-survive-rewetting",
        item="ordered_layers",
        kind="physical",
        metric="Share of the layered gain kept, (V - V_summed)/(V_before - V_summed_before) over the white columns "
        "after the third wetting; share of white in the lowest layer",
        scenario="rewet_default, 128 px: white 6.0 over the dark band, dried; three times clear water 0.3 set on the "
        "band with ordinary resolubility, each dried",
        comparator=">= / <=",
        threshold="kept share >= 0.8; white in the lowest layer <= 0.05",
        source="Gum arabic re-dissolves, so the order is leaky but should hold under clear water. Prototype 0.875.",
        checks=(
            Check("rewet.layered_gain_kept", ">=", 0.8),
            Check("rewet.white_in_lowest_layer", "<=", 0.05),
        ),
        expected_on_baseline="fail",
    ),
    Gate(
        id="COMP-2-white-over-continued-painting",
        item="ordered_layers",
        kind="physical",
        metric="Value of white laid over umber in a painting begun on 0.8.0, against the umber alone",
        scenario="A 64 px painting begun by 0.8.0 (flat-8 burnt umber 3.0 stroke, dried), continued by the engine "
        "with round-4 opaque white 4.5 across the stroke, dried",
        comparator=">",
        threshold="white over umber > umber + 0.2",
        source="Compatibility rule: a 0.8.0 painting follows the same rule as a new one. Measured: prototype 0.718 "
        "against 0.347; 0.8.0 0.527 against 0.347.",
        checks=(Check("paintings_begun_with_reference.white_gain", ">", 0.2),),
        expected_on_baseline="fail",
        correction="Split from the reviewed COMP-2, whose other checks are in C-continue-0.8.0-painting: on 0.8.0 "
        "the white is lighter than the umber by only 0.180, so this check describes the layering the item adds.",
    ),
    Gate(
        id="PHY-8-merge-fidelity",
        item="ordered_layers",
        kind="physical",
        metric="Value over each white column, against V_ref (every layer kept, from snapshots after each dry) and "
        "V_summed",
        scenario="four_glazes, 128 px: dark band; white 4.5 columns; phthalo 0.8 glaze; cadmium red 0.8 glaze; each "
        "dried",
        comparator="<",
        threshold="At every column |V - V_ref| < |V - V_summed|, and |V - V_ref| <= 0.05",
        source="Kubelka 1954: merging is lossless only for layers of the same make-up.",
        checks=(
            Check("four_glazes.nearer_every_layer", "==", True),
            Check("four_glazes.error_to_every_layer", "<=", 0.05),
        ),
        expected_on_baseline="fail",
    ),
    Gate(
        id="INV-5-flow-opens-layers",
        item="ordered_layers",
        kind="physical",
        metric="For each set painted cell reached by water brought by the flow: share of its old paint lying beneath "
        "the new top layer, plus the share lifted",
        scenario="48 px: a 1.6-deep pool beside a dried white line on a dried band",
        comparator=">=",
        threshold="0.99 in every cell",
        source="Layering must not depend on how the water arrived. Prototype 27 of 27 cells at 0.998 or more.",
        checks=(Check("flow_onto_set_paint.least_share", ">=", 0.99),),
        expected_on_baseline="fail",
        correction="Reviewed as an invariant expected to fail on 0.8.0, which keeps no layers; classed with the "
        "physical gates as behaviour the item adds.",
    ),
    Gate(
        id="INV-7-brush-wetting-opens-layers",
        item="ordered_layers",
        kind="physical",
        metric="Cells where white (deposit >= 0.05) landed on set dark paint but less than half the dark lies beneath "
        "it; the share of the dark beneath per column",
        scenario="drybrush_white, 128 px: round 5, white 4.5, full and drained to 0.45/0.25/0.12, over a dried dark "
        "band",
        comparator="== / >=",
        threshold="0 such cells; share of the dark beneath >= 0.9 in every column",
        source="Layering must not depend on how fast the brush's water goes. The review notes that the 0.25 column "
        "may need the lifted paint excluded, as INV-5 does.",
        checks=(
            Check("drybrush_white.cells_not_layered", "==", 0),
            Check("drybrush_white.dark_beneath_share", ">=", 0.9),
        ),
        expected_on_baseline="fail",
        correction="Reclassed from invariant to physical for the reason given for INV-5.",
    ),
    Gate(
        id="REG-1-physics-untouched",
        item="ordered_layers",
        kind="regression",
        metric="Largest absolute difference of water, saturation, suspended, deposited, mask, mask_water and "
        "mask_pigment between the engine and the same engine with its layers held empty",
        scenario="flat wash, bloom, lifting, wet in wet, white_coats, four_glazes, drybrush_white, rewet_default, "
        "set_time, under_darkness (128 px), each painted alone both ways",
        comparator="==",
        threshold="0 (bitwise)",
        source="Design contract: the layers only partition deposited.",
        checks=(Check("physics_untouched.largest_difference", "==", 0.0),),
        extended=True,
        correction="The test double empties the layer fields after every step and every touch of the brush, which "
        "needs no knowledge of how the bookkeeping is written.",
    ),
    Gate(
        id="PERF-1-wet",
        item="ordered_layers",
        kind="performance",
        metric="Wet-phase cost per simulated second over 0.8.0: kernel count, device time and process CPU time; wall time",
        scenario="benchmark.py, 770x540, 6 pigments",
        comparator="<=",
        threshold="kernels, device and CPU <= 1.05; wall time <= 1.10",
        source="Engineering budget.",
        checks=(
            Check("benchmark.wet_kernels_per_second", "<=", 1.05, "baseline"),
            Check("benchmark.wet_device_seconds_per_second", "<=", 1.05, "baseline"),
            Check("benchmark.wet_process_seconds_per_second", "<=", 1.05, "baseline"),
            Check("benchmark.wet_seconds_per_second", "<=", 1.10, "baseline"),
        ),
        correction="Measured by benchmark.py on the binding 770x540 sheet against the baseline recorded alone on 0.8.0, not with both engines interleaved in one process at 256 px; kernel count and device time come from torch.profiler over one simulated second, process CPU time is the median of the repeats.",
    ),
    Gate(
        id="PERF-2-dry",
        item="ordered_layers",
        kind="performance",
        metric="Dry-phase (coarse step) cost per simulated second over 0.8.0: kernels, device time, process CPU time",
        scenario="benchmark.py, 770x540, 6 pigments, no surface water",
        comparator="<=",
        threshold="1.10",
        source="Engineering budget.",
        checks=(
            Check("benchmark.dry_kernels_per_second", "<=", 1.10, "baseline"),
            Check("benchmark.dry_device_seconds_per_second", "<=", 1.10, "baseline"),
            Check("benchmark.dry_process_seconds_per_second", "<=", 1.10, "baseline"),
        ),
        correction="Measured by benchmark.py on the binding 770x540 sheet against the baseline recorded alone on 0.8.0, not with both engines interleaved in one process at 256 px; kernels and device time over ten simulated seconds of coarse steps; process CPU time is the median of the repeats, each summed over five advances of 40 s, since one advance of 10 s takes 14 ms of processor time and a single reading of it is mostly noise.",
    ),
    Gate(
        id="PERF-3-end-to-end",
        item="ordered_layers",
        kind="performance",
        metric="Wall time over 0.8.0 of a pass that lays strokes across layered paint, recording a frame every "
        "0.3 s, then dries",
        scenario="256 px, 6 pigments: dark band and white dried first, so three layers exist; three glaze strokes, "
        "then dry; median of repeats",
        comparator="<=",
        threshold="1.10",
        source="Engineering budget: the cost a painter waits for.",
        checks=(Check("benchmark.end_to_end_seconds", "<=", 1.10, "baseline"),),
        correction="Median of 3 repeats (the review asked for 5), against the recorded baseline.",
    ),
    Gate(
        id="PERF-4-render-layered",
        item="ordered_layers",
        kind="performance",
        metric="render() time over 0.8.0 on a sheet with three non-empty layers",
        scenario="256 px, 6 pigments, on the GPU and on the CPU, median of 9",
        comparator="<=",
        threshold="2.0 on both devices",
        source="render() is about 2.5% of the CPU cost of 0.3 s of painting at 256 px.",
        checks=(
            Check("benchmark.layered_render_seconds", "<=", 2.0, "baseline"),
            Check("benchmark.layered_render_seconds_cpu", "<=", 2.0, "baseline"),
        ),
        correction="Median of 9 against the recorded baseline, not alternated with 0.8.0 in one process.",
    ),
    Gate(
        id="PERF-5-memory-and-state",
        item="ordered_layers",
        kind="performance",
        metric="Extra per-sheet tensor bytes; extra state.pt bytes; each leaving out the binder's gum field",
        scenario="Sheets of 256x256x6, 770x540x6 and 770x540x13",
        comparator="<=",
        threshold="extra memory <= 2*P*H*W*4 + H*W bytes; extra state <= 2*P*H*W*4 + 64 KiB",
        source="Analytic size of the design (two float32 pigment fields and a flag).",
        checks=(
            Check("benchmark.sheet_bytes_256_6_without_gum", "<=", 2 * 6 * 256 * 256 * 4 + 256 * 256, "baseline_plus"),
            Check("benchmark.state_bytes_256_6_without_gum", "<=", 2 * 6 * 256 * 256 * 4 + 65536, "baseline_plus"),
            Check("benchmark.sheet_bytes_770_6_without_gum", "<=", 2 * 6 * 540 * 770 * 4 + 540 * 770, "baseline_plus"),
            Check("benchmark.state_bytes_770_6_without_gum", "<=", 2 * 6 * 540 * 770 * 4 + 65536, "baseline_plus"),
            Check(
                "benchmark.sheet_bytes_770_13_without_gum", "<=", 2 * 13 * 540 * 770 * 4 + 540 * 770, "baseline_plus"
            ),
            Check("benchmark.state_bytes_770_13_without_gum", "<=", 2 * 13 * 540 * 770 * 4 + 65536, "baseline_plus"),
        ),
        correction="Counted leaving out the binder's gum field, for the reason given on P3.",
    ),
)

GATES_BY_ID = {gate.id: gate for gate in GATES}
if len(GATES_BY_ID) != len(GATES):
    raise ValueError("gate ids must be unique")
