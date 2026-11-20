"""Custom Presidio recognizers for Indian identity documents.

Entity names have no country prefix, so tags come out as <AADHAAR>, <PAN>, etc.
"""

from presidio_analyzer import Pattern, PatternRecognizer

# Verhoeff checksum tables (used by Aadhaar numbers).
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _verhoeff_is_valid(number: str) -> bool:
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(digit)]]
    return c == 0


class AadhaarRecognizer(PatternRecognizer):
    """12-digit Aadhaar number, optionally written as 4-4-4 groups; checked with Verhoeff."""

    def __init__(self):
        super().__init__(
            supported_entity="AADHAAR",
            patterns=[Pattern("aadhaar", r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b", 0.5)],
            context=["aadhaar", "aadhar", "uid", "uidai"],
            supported_language="en",
        )

    def validate_result(self, pattern_text: str) -> bool:
        digits = "".join(ch for ch in pattern_text if ch.isdigit())
        return len(digits) == 12 and _verhoeff_is_valid(digits)


def get_indian_recognizers():
    return [
        AadhaarRecognizer(),
        PatternRecognizer(
            supported_entity="PAN",
            # 5 letters, 4 digits, 1 letter; the 4th letter is the holder type (P, C, H, F, ...).
            patterns=[Pattern("pan", r"\b[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]\b", 0.6)],
            context=["pan", "permanent account"],
            supported_language="en",
        ),
        PatternRecognizer(
            supported_entity="PASSPORT",
            patterns=[
                Pattern("indian_passport", r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b", 0.4)
            ],
            context=["passport"],
            supported_language="en",
        ),
        PatternRecognizer(
            supported_entity="VOTER_ID",
            patterns=[Pattern("voter_id", r"\b[A-Z]{3}\d{7}\b", 0.4)],
            context=["voter", "epic", "elector"],
            supported_language="en",
        ),
        PatternRecognizer(
            supported_entity="DRIVING_LICENSE",
            patterns=[
                Pattern("indian_dl", r"\b[A-Z]{2}[- ]?\d{2}[- ]?\d{4}[- ]?\d{7}\b", 0.4)
            ],
            context=["driving", "licence", "license", "dl"],
            supported_language="en",
        ),
        PatternRecognizer(
            supported_entity="GSTIN",
            patterns=[
                Pattern(
                    "gstin",
                    r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
                    0.6,
                )
            ],
            context=["gstin", "gst"],
            supported_language="en",
        ),
    ]
