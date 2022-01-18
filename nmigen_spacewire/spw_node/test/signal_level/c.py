from amaranth import *
from spw_node.src.spw_transmitter import SpWTransmitter, WrongSignallingRate


def test_6_6_1():

    BIT_FREQ_MIN = 2e6

    try:
        dut1 = SpWTransmitter(20e6, BIT_FREQ_MIN)
    except WrongSignallingRate as exc:
        print(exc)
        assert(False)

    dut1._MustUse__silence = True

    try:
        # Expect failure
        dut2 = SpWTransmitter(20e6, BIT_FREQ_MIN - 1)
        assert(False)
    except WrongSignallingRate as exc:
        print(exc)

tests = [test_6_6_1]