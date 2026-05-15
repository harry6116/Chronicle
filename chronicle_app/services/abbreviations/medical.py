import re


MEDICAL_ENTRIES = (
    # Conservative, all-caps clinical/news health terms only. Many clinical
    # abbreviations are unsafe to expand without local context.
    (r"\bB\.?P\b\.?", "blood pressure", 0),
    (r"\bE\.?C\.?G\b\.?", "electrocardiogram", 0),
    (r"\bE\.?E\.?G\b\.?", "electroencephalogram", 0),
    (r"\bI\.?C\.?U\b\.?", "intensive care unit", 0),
    (r"\bE\.?R\b\.?", "emergency room", 0),
    (r"\bE\.?D\b\.?", "emergency department", 0),
    (r"\bG\.?P\b\.?", "general practitioner", 0),
    (r"\bC\.?T\b\.?", "computed tomography", 0),
    (r"\bM\.?R\.?I\b\.?", "magnetic resonance imaging", 0),
    (r"\bD\.?N\.?A\b\.?", "deoxyribonucleic acid", 0),
    (r"\bR\.?N\.?A\b\.?", "ribonucleic acid", 0),
    (r"\bW\.?H\.?O\b\.?", "World Health Organization", 0),
    (r"\bC\.?D\.?C\b\.?", "Centers for Disease Control and Prevention", 0),
)
