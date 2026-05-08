"""Registry detector setup — ordine determina priorità tie-break (D-06)."""
from strategy.setups.a_breakout import detect_a_breakout
from strategy.setups.b_reversal import detect_b_reversal
from strategy.setups.c_compression import detect_c_compression
from strategy.setups.d_pullback import detect_d_pullback

ALL_DETECTORS = [
    detect_a_breakout,
    detect_b_reversal,
    detect_c_compression,
    detect_d_pullback,
]
