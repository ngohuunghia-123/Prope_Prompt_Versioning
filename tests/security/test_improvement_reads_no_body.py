"""AC-2 — the sweep and the read-side types can reach no `call_body`. Structural.

**ADR-0068 §1 is the claim: the evidence is metadata arithmetic, and no stored
request or response body is ever read.** That is what makes a daily unattended
sweep across every workspace defensible at all. A module that read the bodies of
production calls to decide whether a prompt had degraded would be reading
customer conversations on a schedule, with no person in the loop and no request
that asked for it — and it would do so on exactly the code path an injected body
would most like to influence.

**The guarantee is structural rather than behavioural, because ADR-0018 already
decided the database cannot carry it.** `prope_app` holds `SELECT` on
`ledger.call_body` and that privilege is load-bearing for the retention job —
`0003_ledger_tables.py` says so in a comment addressed to this problem by name.
So the thing standing in for a grant is an enumeration: no statement, no import
and no type in this package can reach a body, asserted in both directions.

**`body` means two things in Prope and only one of them is forbidden here.**
`ledger.call_body` holds the request and response of a live call, has no read
path in the MVP, and is what SR-1 and ADR-0018 are about. `registry.revision.body`
holds the PROMPT TEXT, which this module reads deliberately — `remedies.apply`
transforms it, the triage model is given it as spotlighted DATA under SR-9, and
it is the one artefact a person might save. Every exemption below is per FIELD
with a written reason, following `test_no_body_read_path`'s rule that a
legitimate exception is an entry in a list and never a relaxed assertion.

**The candidate body is not in the list read, and that is a decision.** An inbox
row carries a `remedy_family` and a gate delta; the body itself comes back only
from `POST .../accept`, the explicit act. A list endpoint that returned every
open candidate would put model-influenced prompt text into a response nobody
asked a question with — and it would do it in the response people leave open on a
second monitor.
"""

import ast
import re
from pathlib import Path

import pytest

from prope.prompt_improvement import schemas

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "prompt_improvement"

#: The `ledger` tables, whether or not the word `body` appears. Naming
#: `ledger.call_record` here as well as `call_body` is deliberate: the read this
#: module is allowed is `summarise_prompt_calls`, which lives in call-ledger and
#: is reached through prompt-registry (ADR-0055, INT-043). A statement here that
#: named the table would be a second, unclassified reader of it.
FORBIDDEN_TABLES = ("ledger.call_body", "ledger.call_record", "call_body")

#: Body-shaped field names that must not appear on this module's wire types. This
#: is `test_route_table`'s set minus the one exemption below, restated rather than
#: imported so that a change to the route-table list cannot silently widen this.
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "request_body",
        "response_body",
        "byte_size",
        "body",
        "bytes",
        "payload",
        "request_payload",
        "response_payload",
        "raw_body",
        "call_body",
    }
)

#: ``schema.field -> the written reason this one is not the body store's.``
SANCTIONED_BODY_FIELDS = {
    "ProposalAccepted.candidate_body": (
        "The proposed PROMPT TEXT, produced by `remedies.apply` from `registry.revision.body`. "
        "It is what the person is about to see in an editor and save as a revision themselves "
        "(SR-6), so it must cross the wire — on the accept route only, never in a list."
    ),
}


def _package_modules() -> list[Path]:
    modules = sorted(PACKAGE.rglob("*.py"))
    assert modules, f"no modules found under {PACKAGE}"
    return modules


def _code_only(module: Path) -> str:
    """Source with docstrings and comments removed, and SQL literals kept.

    The distinction is the whole design of the check below. Four modules name
    ``ledger.call_record`` in prose to say where the metadata comes from, and
    those are the sentences this file most wants people to keep writing — a
    module that explains its data source is not a module reading it. What must
    not exist is a STATEMENT, and a statement lives in a string literal that is
    not a docstring.
    """
    source = module.read_text(encoding="utf-8")
    lines = source.splitlines()

    for node in ast.walk(ast.parse(source)):
        if not isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and first.end_lineno is not None
        ):
            for index in range(first.lineno - 1, first.end_lineno):
                lines[index] = ""

    return "\n".join(re.sub(r"#.*$", "", line) for line in lines)


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_no_statement_in_this_module_names_a_ledger_table(module: Path) -> None:
    """The sweep's read of production traffic is counts, and only counts.

    `summarise_prompt_calls` returns a `PromptCallWindow` — fourteen integers, a
    timestamp and nothing else. It is reached through prompt-registry, after that
    module has authorised `prompt.read` on the row. A statement here naming a
    ledger table would be a reader outside that check, on a code path that runs
    without any person having asked for anything.
    """
    named = [table for table in FORBIDDEN_TABLES if table in _code_only(module)]
    assert named == [], (
        f"{module.name} names {named} in CODE. The evidence is metadata arithmetic "
        "(ADR-0068 §1) and the only sanctioned read of production traffic is "
        "`summarise_prompt_calls`, through prompt-registry, per prompt, behind `prompt.read` "
        "(ADR-0055, INT-043)."
    )


def test_the_window_type_cannot_carry_a_body_or_a_call_id() -> None:
    """**The type is what makes the claim, not the query.**

    Everything the detectors see arrives as a `PromptCallWindow`. If that type
    grows a body field, every assertion above still passes and the module starts
    reading conversations — so the type is checked directly, from this module's
    side, even though it is declared in another one.

    The absent `call_id` matters as much as the absent body. A caller reading
    windows can compute that truncation rose and cannot reconstruct WHICH request
    truncated, which is exactly the amount of information a sweep needs and the
    most it should have.
    """
    from prope.call_ledger.seams import PromptCallWindow

    fields = set(PromptCallWindow.__dataclass_fields__)

    assert not fields & FORBIDDEN_FIELD_NAMES, sorted(fields & FORBIDDEN_FIELD_NAMES)
    assert not {name for name in fields if name.endswith("_id")}, sorted(fields)
    assert "call_id" not in fields


def test_no_wire_type_carries_a_body_field_without_a_written_reason() -> None:
    """Every exemption is per field, named, and still real.

    The second half is what keeps the list honest: an exemption for a field that
    no longer exists is a licence somebody will reuse for the next one.
    """
    offenders: list[str] = []
    for name in dir(schemas):
        model = getattr(schemas, name)
        fields = getattr(model, "model_fields", None)
        if not isinstance(fields, dict):
            continue
        for field in fields:
            if field.lower() in FORBIDDEN_FIELD_NAMES or field.endswith("_body"):
                if f"{name}.{field}" not in SANCTIONED_BODY_FIELDS:
                    offenders.append(f"{name}.{field}")

    assert offenders == [], f"{offenders} — add a written reason or remove the field."

    for entry in SANCTIONED_BODY_FIELDS:
        model_name, field = entry.split(".")
        model = getattr(schemas, model_name, None)
        assert model is not None, f"{entry} exempts a schema that no longer exists"
        assert field in model.model_fields, f"{entry} exempts a field that no longer exists"


def test_the_candidate_body_is_absent_from_every_list_read() -> None:
    """**A queue does not hand out prompt text.** The inbox is a list of codes.

    `LIST_INBOX` and `FINDINGS_FOR_PROMPT` are the two statements a person's
    screen is built from, and neither selects `candidate_body`. The body is
    reachable only through `READ_PROPOSAL` and `DECIDE_PROPOSAL` — the accept
    path, which is one proposal, one deliberate act, and an authorisation against
    `revision.create` rather than `prompt.read`.

    Asserted over the SQL rather than over the response model because the two can
    disagree in the direction that matters: a statement that selects a column the
    schema drops has already read it into the process, into a row object, and
    into whatever a future log line decides to include.
    """
    source = (PACKAGE / "repository.py").read_text(encoding="utf-8")
    statements = dict(
        re.findall(r'^([A-Z_]+) = text\("""(.*?)"""\)', source, re.MULTILINE | re.DOTALL)
    )

    for name in ("LIST_INBOX", "FINDINGS_FOR_PROMPT"):
        assert name in statements, f"{name} is gone; this test would pass vacuously"
        assert "candidate_body" not in statements[name], (
            f"{name} selects candidate_body. The inbox renders a remedy family and a gate "
            "delta; the body belongs to the accept route alone (SR-6)."
        )

    reads_the_body = {
        name for name, body in statements.items() if "candidate_body" in body
    }
    assert reads_the_body == {"OPEN_PROPOSAL", "READ_PROPOSAL", "DECIDE_PROPOSAL"}, sorted(
        reads_the_body
    )


def test_the_list_read_schema_has_no_field_a_body_could_occupy() -> None:
    """The wire half of the statement above, so the two must both be changed.

    `ProposalRead` is what an inbox row's proposal looks like: an id, a kind, a
    family, a gate delta and an expiry. There is deliberately no optional body
    field sitting empty and waiting to be populated, because an optional field is
    a decision somebody makes once and a missing field is a change somebody has
    to justify.
    """
    fields = set(schemas.ProposalRead.model_fields)

    assert not [name for name in fields if name.endswith("_body")], sorted(fields)
    assert fields == {
        "proposal_id",
        "remedy_kind",
        "remedy_family",
        "gate_delta",
        "expires_at",
    }, sorted(fields)


def test_the_triage_model_receives_exactly_four_named_inputs() -> None:
    """SR-9, which is an enumeration and NOT an absence — and the difference matters.

    The prompt body **does** reach the triage model. It is given as spotlighted
    DATA, the signature says so in a security-boundary paragraph, and the model's
    output is bounded to a detector id, a rank, a family from a set it was handed
    and one sentence that passes the redaction rail before storage. That is a
    considered position rather than an oversight: a ranking model that cannot see
    the prompt cannot tell a truncation finding on a summariser from one on a
    chatbot.

    What must never arrive is the OTHER body — a stored request or response from
    `ledger.call_body`, which is a customer's conversation and is what SR-1
    forbids. So this pins the input set rather than banning a word: a fifth field
    named `call_samples` or `recent_outputs` fails here, at the one boundary
    where private data would cross into a component whose output a person reads.
    """
    tree = ast.parse((PACKAGE / "dspy_program.py").read_text(encoding="utf-8"))

    inputs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TriageAnomalies":
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(
                    statement.target, ast.Name
                ):
                    continue
                call = statement.value
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "InputField"
                ):
                    inputs.append(statement.target.id)

    assert inputs, "TriageAnomalies not found — the assertion below would pass vacuously"
    assert set(inputs) == {
        "prompt_title",
        "prompt_body",
        "anomalies",
        "reachable_families",
    }, sorted(inputs)


def test_the_untrusted_inputs_are_spotlighted_on_the_field_itself() -> None:
    """The other half of SR-9: *the body is DATA and may not instruct the model.*

    Two of the four inputs are attacker-influenceable — the body was written by
    somebody, and the anomaly figures are derived from traffic somebody caused.
    Both carry an explicit ``UNTRUSTED DATA`` marker on the field description, not
    only in the signature's prose, because the description is what travels beside
    the value.

    **This is a weak control and is named as one.** Spotlighting lowers the odds
    and does not eliminate them; what actually bounds the damage is that the
    model's entire output is four fields, none of which is a body, and its one
    free-text field is a single sentence that passes `redact_evidence` before it
    is stored.
    """
    tree = ast.parse((PACKAGE / "dspy_program.py").read_text(encoding="utf-8"))

    marked: dict[str, bool] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TriageAnomalies":
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(
                    statement.target, ast.Name
                ):
                    continue
                call = statement.value
                if not isinstance(call, ast.Call):
                    continue
                described = " ".join(
                    keyword.value.value
                    for keyword in call.keywords
                    if keyword.arg == "desc" and isinstance(keyword.value, ast.Constant)
                )
                marked[statement.target.id] = "UNTRUSTED DATA" in described

    assert marked.get("prompt_body") is True, "the released body is somebody's text"
    assert marked.get("anomalies") is True, "the figures are derived from traffic somebody caused"


def test_the_evidence_line_passes_its_rail_before_storage_not_before_render() -> None:
    """SR-9. A rail applied at render is a rail somebody bypasses with a client.

    The one sentence a model writes in this module is quoted back to a person, so
    it goes through `redact_evidence` — URL-free, markdown-link-free,
    credential-redacted — on the way INTO the row. Asserted structurally here;
    what the rail actually strips is `prompt_readiness`'s test, because it is
    `prompt_readiness`'s function and one definition of a safe sentence is the
    point of importing it rather than copying it.
    """
    source = (PACKAGE / "triage.py").read_text(encoding="utf-8")

    assert "bounded_evidence" in source or "redact_evidence" in source, (
        "nothing in triage.py applies the output rail; an evidence line would reach a row raw"
    )
