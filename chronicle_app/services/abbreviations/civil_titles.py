import re


CIVIL_TITLE_ENTRIES = (
    (r"\bGov\b\.?", "Governor"),
    (r"\bHon\b\.?", "Honourable"),
    (r"\bBros\b\.?", "Brothers"),
    (r"\bRt\.?\s*Hon\b\.?", "Right Honourable"),
    (r"\bRev\b\.?", "Reverend"),
    (r"\bSen\b\.?", "Senator"),
    (r"\bRep\b\.?", "Representative"),
    (r"\bJ\.?P\b\.?", "Justice of the Peace", 0),
    (r"\bM\.?P\b\.?", "Member of Parliament", 0),
    (r"\bM\.?L\.?A\b\.?", "Member of the Legislative Assembly", 0),
    (r"\bM\.?L\.?C\b\.?", "Member of the Legislative Council", 0),
)
