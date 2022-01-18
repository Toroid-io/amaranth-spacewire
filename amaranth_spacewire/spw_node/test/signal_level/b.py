from amaranth import *
from amaranth.sim import Simulator, Delay, Settle
from spw_node.src.spw_transmitter import SpWTransmitter
from spw_node.test.spw_test_utils import *
import random

def test_6_3_2_b():

    SRCFREQ = 20e6
    # Use reset frequency to avoid managing two frequencies
    TX_FREQ = 10e6
    BIT_TIME = 1/TX_FREQ
    CHAR_TIME = BIT_TIME * 4

    dut = SpWTransmitter(SRCFREQ, TX_FREQ, debug=True)

    sim = Simulator(dut)
    sim.add_clock(1/SRCFREQ)

    random.seed()

    count = [0, 0, 0, 0]

    def assert_ds_order():
        yield dut.i_reset.eq(1)
        while not (yield dut.o_debug_encoder_reset_feedback):
            yield
        # Now see the state of the DS signals
        d = yield dut.o_d
        s = yield dut.o_s
        if d and s:
            count[0] = count[0] + 1
            # First S
            assert not (yield dut.o_s)
            assert (yield dut.o_d)
            # Then D
            yield Delay(BIT_TIME)
            assert not (yield dut.o_s)
            assert not (yield dut.o_d)
        elif not d and s:
            count[1] = count[1] + 1
            # First S
            assert not (yield dut.o_s)
            assert not (yield dut.o_d)
            # Then D
            yield Delay(BIT_TIME)
            assert not (yield dut.o_s)
            assert not (yield dut.o_d)
        elif d and not s:
            count[2] = count[2] + 1
            # First S
            assert not (yield dut.o_s)
            assert (yield dut.o_d)
            # Then D
            yield Delay(BIT_TIME)
            assert not (yield dut.o_s)
            assert not (yield dut.o_d)
        else:
            count[3] = count[3] + 1
            # First S
            assert not (yield dut.o_s)
            assert not (yield dut.o_d)
            # Then D
            yield Delay(BIT_TIME)
            assert not (yield dut.o_s)
            assert not (yield dut.o_d)
        yield dut.i_reset.eq(0)

    def test():
        yield dut.i_reset.eq(1)
        for _ in range(ds_sim_period_to_ticks(20e-6, SRCFREQ)):
            yield
        yield dut.i_reset.eq(0)
        for _ in range(100):
            t = random.randint(6, 147)
            for _ in range(ds_sim_period_to_ticks(t * 1e-6, SRCFREQ)):
                yield
            yield from assert_ds_order()

    sim.add_sync_process(test)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run()

    for i in range(4):
        print("Tested {0} times case {1}".format(count[i], i))
        # Given that we wait encoder_reset_feedback, this means the encoder was
        # reset and Strobe signal MUST be reset by that time.
        assert(count[0] == 0)
        assert(count[1] == 0)


tests = [test_6_3_2_b]