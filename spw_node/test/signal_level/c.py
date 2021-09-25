from nmigen import *
from nmigen.sim import Simulator, Delay, Settle
from spw_node.src.spw_transmitter import SpWTransmitter, WrongSignallingRate


def test_6_6_1():

    BIT_FREQ_MIN = 2e6

    try:
        dut1 = SpWTransmitter(10e6, BIT_FREQ_MIN)
    except WrongSignallingRate as exc:
        print(exc)
        assert(False)

    try:
        # Expect failure
        dut2 = SpWTransmitter(10e6, BIT_FREQ_MIN - 1)
        assert(False)
    except WrongSignallingRate as exc:
        print(exc)

    sim = Simulator(dut1)

    # Avoid unused warning
    def dummy_test():
        yield Delay(1e-6)

    sim.add_process(dummy_test)

    sim.run()

tests = [test_6_6_1]