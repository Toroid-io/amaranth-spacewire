from amaranth import *
from amaranth.sim import Simulator, Delay, Settle
from spw_node.src.spw_node import SpWNode
from spw_node.src.spw_transmitter import SpWTransmitterStates
from spw_node.test.spw_test_utils import *

def test_7_3_b():
    SRCFREQ = 30e6
    SIMSTART = 20e-6
    TX_FREQ = 10e6
    BIT_TIME = 1/TX_FREQ
    CHAR_TIME = BIT_TIME * 4

    dut = SpWNode(srcfreq=SRCFREQ, txfreq=TX_FREQ, disconnect_delay=1, debug=True)

    sim = Simulator(dut)
    sim.add_clock(1/SRCFREQ)

    def init():
        yield dut.link_disabled.eq(0)
        yield dut.link_start.eq(1)
        yield dut.autostart.eq(1)
        yield dut.r_en.eq(0)
        yield dut.soft_reset.eq(0)
        yield dut.tick_input.eq(0)
        yield dut.w_en.eq(0)
        yield Settle()

    def send_nulls():
        yield Delay(SIMSTART)
        for _ in range(5):
            yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        yield from ds_sim_send_fct(dut.d_input, dut.s_input, BIT_TIME)
        for _ in range(50):
            yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)

    def monitor_send_null():
        yield Delay(SIMSTART)
        for _ in range(ds_sim_period_to_ticks(200e-6, SRCFREQ)):
            if ( (yield dut.debug_tr.o_debug_fsm_state == SpWTransmitterStates.WAIT) &
                 (yield dut.debug_tr.o_ready) &
                 ~ (yield dut.debug_tr.i_send_char) &
                 ~ (yield dut.debug_tr.i_send_eep) &
                 ~ (yield dut.debug_tr.i_send_eop) &
                 ~ (yield dut.debug_tr.i_send_esc) &
                 ~ (yield dut.debug_tr.i_send_fct) &
                 ~ (yield dut.debug_tr.i_send_time)):
                while(yield dut.debug_tr.o_debug_fsm_state == SpWTransmitterStates.WAIT):
                    yield Delay(BIT_TIME/4)
                assert(yield dut.debug_tr.o_debug_fsm_state == SpWTransmitterStates.SEND_NULL_A)
            else:
                yield

    sim.add_process(init)
    sim.add_process(send_nulls)
    sim.add_sync_process(monitor_send_null)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run()

tests = [test_7_3_b]