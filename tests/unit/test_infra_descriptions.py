"""Security group descriptions in infra/ must use the characters EC2 accepts.

EC2 rejects a security group or rule description with any other character (an
apostrophe broke the Google sign-in apply), and neither terraform validate nor
plan catches it, so this test does.
"""

import re
from pathlib import Path

INFRA = Path(__file__).resolve().parents[2] / "infra"

SECURITY_GROUP_TYPES = (
    "aws_security_group",
    "aws_vpc_security_group_ingress_rule",
    "aws_vpc_security_group_egress_rule",
)

# The set EC2 documents for security group and rule descriptions.
ALLOWED = re.compile(r"^[a-zA-Z0-9. _\-:/()#,@\[\]+=&;{}!$*]{0,255}$")

RESOURCE = re.compile(r'^resource "(\w+)" "(\w+)" \{$')
DESCRIPTION = re.compile(r'^\s*description\s*=\s*"(.*)"\s*$')


def _security_group_descriptions() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(INFRA.glob("*.tf")):
        current: str | None = None
        for line in path.read_text().splitlines():
            if match := RESOURCE.match(line):
                kind, name = match.groups()
                current = f"{kind}.{name}" if kind in SECURITY_GROUP_TYPES else None
            elif line == "}":
                current = None
            elif current and (match := DESCRIPTION.match(line)):
                found.append((current, match.group(1)))
    return found


def test_security_group_descriptions_use_allowed_characters() -> None:
    descriptions = _security_group_descriptions()

    assert len(descriptions) >= 8, "parser found too few security group descriptions"
    bad = [(name, text) for name, text in descriptions if not ALLOWED.match(text)]
    assert bad == []


def test_the_pattern_rejects_an_apostrophe() -> None:
    assert not ALLOWED.match("HTTPS to Google's sign-in endpoints")
    assert ALLOWED.match("HTTPS to the Google sign-in endpoints")
