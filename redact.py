import re

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from indian_recognizers import get_indian_recognizers

analyzer = AnalyzerEngine()
for recognizer in get_indian_recognizers():
    analyzer.registry.add_recognizer(recognizer)
anonymizer = AnonymizerEngine()

# Tag text per entity type; anything not listed keeps the default <ENTITY_TYPE> tag.
operators = {"PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<phone>"})}
# Drop the "US_" prefix from every US tag, e.g. <US_ITIN> -> <ITIN>.
operators.update(
    {
        entity: OperatorConfig(
            "replace", {"new_value": f"<{entity.removeprefix('US_')}>"}
        )
        for entity in analyzer.get_supported_entities()
        if entity.startswith("US_")
    }
)
# Bank account numbers use their own tag.
operators["US_BANK_NUMBER"] = OperatorConfig("replace", {"new_value": "<bank_no>"})


# spaCy's name/place/date model. It scores bare digit strings at 0.85, so its
# matches on digit-only tokens are almost always wrong (e.g. "123456789" as a date).
NER_ENTITY_TYPES = {"PERSON", "LOCATION", "NRP", "DATE_TIME"}
# Words that look like places to spaCy but are not personal data here.
ALLOW_LIST = ["US", "USA"]


def _is_digit_token(text: str) -> bool:
    return any(ch.isdigit() for ch in text) and not any(ch.isspace() for ch in text)


def _priority(r) -> tuple:
    # ID patterns beat phone numbers, and phone numbers beat spaCy NER matches.
    if r.entity_type in NER_ENTITY_TYPES:
        tier = 0
    elif r.entity_type == "PHONE_NUMBER":
        tier = 1
    else:
        tier = 2
    return (tier, r.score, r.end - r.start)


def keep_non_overlapping(results):
    """Pick a non-overlapping set of entities, highest priority first.

    A match is dropped if it overlaps one already kept.
    """
    kept = []
    for r in sorted(results, key=_priority, reverse=True):
        if all(r.end <= k.start or r.start >= k.end for k in kept):
            kept.append(r)
    return kept


SSN_SHAPE = re.compile(r"^\d{3}[- ]\d{2}[- ]\d{4}$")
# A document keyword on its own, e.g. "Passport", that spaCy sometimes reads as a name.
DOCUMENT_KEYWORD_WORD = re.compile(
    r"passport|voter|driving|licen[cs]e|pan|gstin", re.IGNORECASE
)

# Keyword-driven rules: the value after a document keyword is tagged even when its
# format is unusual or malformed (typed-in IDs often are). The value must be at
# least 4 characters and contain a digit; an optional second token must also contain a digit.
_VALUE = (
    r"(?=[A-Za-z0-9-]*\d)(?=[A-Za-z0-9-]{4})[A-Za-z0-9-]+"
    r"(?:\s+[A-Za-z0-9-]*\d[A-Za-z0-9-]*)?"
)
_KEYWORD_RULES = [
    ("PASSPORT", r"passport"),
    ("VOTER_ID", r"voter\s*id"),
    ("DRIVING_LICENSE", r"driving\s+licen[cs]e"),
    ("PAN", r"pan"),
    ("GSTIN", r"gstin"),
]
KEYWORD_PATTERNS = [
    (
        entity,
        re.compile(
            rf"\b(?:{kw})(?:\s+(?:no\.?|number|num))?(?:\s*[:#]\s*|\s+)(?P<value>{_VALUE})",
            re.IGNORECASE,
        ),
    )
    for entity, kw in _KEYWORD_RULES
]


def keyword_results(text: str) -> list:
    found = []
    for entity, pattern in KEYWORD_PATTERNS:
        for m in pattern.finditer(text):
            found.append(
                RecognizerResult(
                    entity_type=entity,
                    start=m.start("value"),
                    end=m.end("value"),
                    score=0.9,
                )
            )
    return found


def redact(text: str) -> str:
    results = analyzer.analyze(text=text, language="en", allow_list=ALLOW_LIST)
    results = results + keyword_results(text)
    kept_results = []
    for r in results:
        matched = text[r.start : r.end]
        if r.entity_type in NER_ENTITY_TYPES and (
            _is_digit_token(matched) or DOCUMENT_KEYWORD_WORD.fullmatch(matched)
        ):
            continue
        # US phone numbers are never written 3-2-4, so a phone match in that shape is an SSN.
        if r.entity_type == "PHONE_NUMBER" and SSN_SHAPE.match(matched):
            r.entity_type = "US_SSN"
        kept_results.append(r)
    results = kept_results
    results = keep_non_overlapping(results)
    return anonymizer.anonymize(
        text=text, analyzer_results=results, operators=operators
    ).text


if __name__ == "__main__":
    while True:
        text = input("\nType a sentence (or 'q' to quit): ")
        if text.strip().lower() == "q":
            break
        print("Redacted:", redact(text))
