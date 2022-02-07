from amaranth import *
from amaranth.sim import Simulator, Delay, Settle
from spw_node.src.spw_node import SpWNode
from spw_node.src.spw_transmitter import SpWTransmitterStates
from spw_node.test.spw_test_utils import *

def test_7_3_d():
    SRCFREQ = 30e6
    SIMSTART = 20e-6
    TX_FREQ = 10e6
    BIT_TIME = 1/TX_FREQ
    CHAR_TIME = BIT_TIME * 4

    tick = Signal()

    m = Module()
    m.submodules.dut = dut = SpWNode(srcfreq=SRCFREQ, txfreq=TX_FREQ, disconnect_delay=1, debug=True, time_master=True)
    m.d.comb += [
        dut.link_disabled.eq(0),
        dut.link_start.eq(1),
        dut.autostart.eq(1),
        dut.r_en.eq(0),
        dut.soft_reset.eq(0),
        dut.w_en.eq(0),
        dut.tick_input.eq(tick)
    ]

    def send_nulls():
        yield Delay(SIMSTART)
        for _ in range(5):
            yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)
        yield from ds_sim_send_fct(dut.i_d, dut.i_s, BIT_TIME)
        for _ in range(100):
            yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)

    def ticks():
        yield Delay(SIMSTART)
        for _ in range(50):
            for _ in range(ds_sim_period_to_ticks(10e-6, SRCFREQ)):
                yield
            yield tick.eq(1)
            yield
            yield tick.eq(0)

    # This test does not work because the simulator has troubles with multi
    # clock simulations.
    def test_time_codes():
        time_counter = 0
        yield Delay(SIMSTART)
        for _ in range(50):
            while (yield dut.o_debug_tr_send_time == 0):
                yield
            time_counter = yield dut.o_debug_time_counter
            print(time_counter)
            while (yield dut.o_debug_tr_send_time == 1):
                yield
            while (yield dut.o_debug_tr_fsm_state != SpWTransmitterStates.SEND_TIME_B):
                yield
            #assert(dut.o_debug_tr_sr_input[:6] == time_counter)

    sim = Simulator(m)
    sim.add_clock(1/SRCFREQ)
    sim.add_clock(1/TX_FREQ, domain="tx")
    sim.add_process(send_nulls)
    sim.add_sync_process(ticks)
    sim.add_sync_process(test_time_codes)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run()

tests = [test_7_3_d]