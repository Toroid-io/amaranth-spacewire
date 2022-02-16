import unittest
import random
import logging

from amaranth import *
from amaranth.sim import Simulator, Delay, Settle
from amaranth_spacewire import SpWTransmitter
from spw_test_utils import *

SRCFREQ = 20e6
# Use reset frequency to avoid managing two frequencies
TX_FREQ = 10e6
BIT_TIME = 1/TX_FREQ
CHAR_TIME = BIT_TIME * 4

class test632b(unittest.TestCase):
    def setUp(self):
        self.dut = SpWTransmitter(SRCFREQ, TX_FREQ, debug=True)

        self.sim = Simulator(self.dut)
        self.sim.add_clock(1/SRCFREQ)

        random.seed()
        self.count = [0, 0, 0, 0]

    def assert_ds_order(self):
        yield self.dut.i_reset.eq(1)
        while not (yield self.dut.o_debug_encoder_reset_feedback):
            yield
        # Now see the state of the DS signals
        d = yield self.dut.o_d
        s = yield self.dut.o_s
        if d and s:
            self.count[0] = self.count[0] + 1
            # First S
            assert not (yield self.dut.o_s)
            assert (yield self.dut.o_d)
            # Then D
            yield Delay(BIT_TIME)
            assert not (yield self.dut.o_s)
            assert not (yield self.dut.o_d)
        elif not d and s:
            self.count[1] = self.count[1] + 1
            # First S
            assert not (yield self.dut.o_s)
            assert not (yield self.dut.o_d)
            # Then D
            yield Delay(BIT_TIME)
            assert not (yield self.dut.o_s)
            assert not (yield self.dut.o_d)
        elif d and not s:
            self.count[2] = self.count[2] + 1
            # First S
            assert not (yield self.dut.o_s)
            assert (yield self.dut.o_d)
            # Then D
            yield Delay(BIT_TIME)
            assert not (yield self.dut.o_s)
            assert not (yield self.dut.o_d)
        else:
            self.count[3] = self.count[3] + 1
            # First S
            assert not (yield self.dut.o_s)
            assert not (yield self.dut.o_d)
            # Then D
            yield Delay(BIT_TIME)
            assert not (yield self.dut.o_s)
            assert not (yield self.dut.o_d)
        yield self.dut.i_reset.eq(0)

    def loop(self):
        yield self.dut.i_reset.eq(1)
        for _ in range(ds_sim_period_to_ticks(20e-6, SRCFREQ)):
            yield
        yield self.dut.i_reset.eq(0)
        for _ in range(100):
            t = random.randint(6, 147)
            for _ in range(ds_sim_period_to_ticks(t * 1e-6, SRCFREQ)):
                yield
            yield from self.assert_ds_order()

    def test_spec_6_3_2_b(self):
        self.sim.add_sync_process(self.loop)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.dut.ports()):
            self.sim.run()

        logging.debug("")
        for i in range(4):
            logging.debug("Tested {0} times case {1}".format(self.count[i], i))
            # Given that we wait encoder_reset_feedback, this means the encoder was
            # reset and Strobe signal MUST be reset by that time.
            assert(self.count[0] == 0)
            assert(self.count[1] == 0)
