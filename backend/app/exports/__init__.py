"""BOQ exports (G7) — JSON/XLSX/PDF writers + export router (spec v3 §7.14).

Every exported line carries material, quantity, confidence_status,
size_source and the unpriced flag. Unpriced lines render flagged
``UNPRICED — review required`` — never as $0.
"""

UNPRICED_LABEL = "UNPRICED — review required"
