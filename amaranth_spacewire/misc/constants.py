from amaranth import *

TX_FREQ_RESET       = 10e6
MIN_TX_FREQ_USER    = 2e6
CHAR_FCT            = Const(0b100000000)
CHAR_ESC            = Const(0b100000011)
CHAR_EOP            = Const(0b100000010)
CHAR_EEP            = Const(0b100000001)
MAX_TX_CREDIT       = 56
MAX_TOKENS          = 7

def MAX_RX_CREDIT(tokens):
    return 56 if tokens >= 7 else tokens * 8
