"""Contract tests for the WoT Thing Descriptions in src/things.

Binding references: plan section 5.7 (WoT TD 1.1, no nosec, forms, properties
aligned with the JSON Schemas) and CONTRACTS.md sections 1-3 (MQTT endpoint,
topic layout, measurement fields and bounds). The TD measurement properties are
cross-checked programmatically against the corresponding JSON Schemas so the
two artefact families cannot drift apart silently.
"""

import json
import re

import pytest

from conftest import SCHEMA_DIR, THINGS_DIR

TD_11_CONTEXT_URI = "https://www.w3.org/2022/wot/td/v1.1"

# TD file -> corresponding device JSON Schema file
TD_TO_SCHEMA = {
    "smartwatch.td.json": "smartwatch-v1.schema.json",
    "smart-ring.td.json": "smart-ring-v1.schema.json",
    "smart-clothing.td.json": "smart-clothing-v1.schema.json",
}

TD_FILES = sorted(TD_TO_SCHEMA)

# CONTRACTS.md section 1: port 8883 TLS, topic c2dt/{egw_id}/{device_uuid}/telemetry.
# {{EGW_HOST}} is the documented deployment-time host placeholder.
EXPECTED_FORM_HREF = "mqtts://{{EGW_HOST}}:8883/c2dt/{egw_id}/{device_uuid}/telemetry"
FORM_HREF_RE = re.compile(
    r"^mqtts://\{\{EGW_HOST\}\}:8883/c2dt/\{egw_id\}/\{device_uuid\}/telemetry$"
)


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_td(filename: str) -> dict:
    return _load_json(THINGS_DIR / filename)


def _measurement_fields(schema: dict) -> dict:
    """Schema-declared measurement fields (everything except the device_type const)."""
    return {k: v for k, v in schema["properties"].items() if k != "device_type"}


def _iter_forms(td: dict):
    for affordance_kind in ("properties", "actions", "events"):
        for affordance in td.get(affordance_kind, {}).values():
            for form in affordance.get("forms", []):
                yield form


# ---------------------------------------------------------------------------
# Parsing and TD 1.1 basics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("td_file", TD_FILES)
def test_td_parses_with_title_and_version(td_file):
    td = _load_td(td_file)
    assert td["title"]
    assert td["version"]["instance"] == "1.0.0"


@pytest.mark.parametrize("td_file", TD_FILES)
def test_td_context_is_wot_td_11(td_file):
    context = _load_td(td_file)["@context"]
    if isinstance(context, str):
        assert context == TD_11_CONTEXT_URI
    else:
        assert isinstance(context, list)
        assert context[0] == TD_11_CONTEXT_URI


# ---------------------------------------------------------------------------
# Security: no nosec anywhere (plan section 5.7), basic scheme in use
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("td_file", TD_FILES)
def test_td_contains_no_nosec(td_file):
    raw = (THINGS_DIR / td_file).read_text(encoding="utf-8")
    assert "nosec" not in raw.lower()


@pytest.mark.parametrize("td_file", TD_FILES)
def test_td_uses_basic_security_scheme(td_file):
    td = _load_td(td_file)
    definitions = td["securityDefinitions"]
    assert "basic_sc" in definitions
    assert definitions["basic_sc"]["scheme"] == "basic"
    for definition in definitions.values():
        assert definition["scheme"] != "nosec"
    security = td["security"]
    if isinstance(security, str):
        security = [security]
    assert security == ["basic_sc"]


# ---------------------------------------------------------------------------
# Measurement properties mirror the JSON Schemas exactly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("td_file", TD_FILES)
def test_td_properties_match_schema_fields_exactly(td_file):
    td = _load_td(td_file)
    schema = _load_json(SCHEMA_DIR / TD_TO_SCHEMA[td_file])
    measurement = _measurement_fields(schema)
    assert set(td["properties"]) == set(measurement)


@pytest.mark.parametrize("td_file", TD_FILES)
def test_td_property_types_and_bounds_match_schema(td_file):
    td = _load_td(td_file)
    schema = _load_json(SCHEMA_DIR / TD_TO_SCHEMA[td_file])
    for field, schema_def in _measurement_fields(schema).items():
        td_prop = td["properties"][field]
        assert td_prop["type"] == schema_def["type"], field
        assert td_prop["minimum"] == schema_def["minimum"], field
        assert td_prop["maximum"] == schema_def["maximum"], field


@pytest.mark.parametrize("td_file", TD_FILES)
def test_td_properties_read_only_with_unit(td_file):
    td = _load_td(td_file)
    for field, td_prop in td["properties"].items():
        assert td_prop["readOnly"] is True, field
        assert isinstance(td_prop["unit"], str) and td_prop["unit"], field


# ---------------------------------------------------------------------------
# Forms: mqtts scheme and CONTRACTS topic pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("td_file", TD_FILES)
def test_all_forms_use_mqtts_and_contract_topic(td_file):
    td = _load_td(td_file)
    forms = list(_iter_forms(td))
    assert forms, "TD must declare at least one form"
    for form in forms:
        href = form["href"]
        assert href.startswith("mqtts://"), href
        assert FORM_HREF_RE.match(href), href
        assert form["contentType"] == "application/json"


@pytest.mark.parametrize("td_file", TD_FILES)
def test_every_property_has_a_form(td_file):
    td = _load_td(td_file)
    for field, td_prop in td["properties"].items():
        assert td_prop.get("forms"), field


@pytest.mark.parametrize("td_file", TD_FILES)
def test_telemetry_event_form(td_file):
    td = _load_td(td_file)
    event = td["events"]["telemetry"]
    forms = event["forms"]
    assert len(forms) >= 1
    form = forms[0]
    assert form["href"] == EXPECTED_FORM_HREF
    assert form["contentType"] == "application/json"
    assert form["mqv:controlPacket"] == "publish"


@pytest.mark.parametrize("td_file", TD_FILES)
def test_uri_variables_declared_for_topic_template(td_file):
    td = _load_td(td_file)
    uri_variables = td["uriVariables"]
    assert "egw_id" in uri_variables
    assert "device_uuid" in uri_variables


# ---------------------------------------------------------------------------
# Link back to the JSON Schema $id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("td_file", TD_FILES)
def test_td_links_to_schema_id(td_file):
    td = _load_td(td_file)
    schema = _load_json(SCHEMA_DIR / TD_TO_SCHEMA[td_file])
    schema_links = [link for link in td["links"] if link.get("rel") == "schema"]
    assert len(schema_links) == 1
    assert schema_links[0]["href"] == schema["$id"]
