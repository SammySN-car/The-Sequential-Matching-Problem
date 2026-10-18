"""Executable registry: method_id -> decide function. Rerun gen_policies.py after
any change (every launcher imports its decide from here)."""
from methods_a import DECISIONS as DECISIONS_A
from methods_b import DECISIONS as DECISIONS_B
from methods_c import DECISIONS as DECISIONS_C
from methods_d import DECISIONS as DECISIONS_D
from methods_e import DECISIONS as DECISIONS_E

REGISTRY = {}
REGISTRY.update(DECISIONS_A)
REGISTRY.update(DECISIONS_B)
REGISTRY.update(DECISIONS_C)
REGISTRY.update(DECISIONS_D)
REGISTRY.update(DECISIONS_E)
