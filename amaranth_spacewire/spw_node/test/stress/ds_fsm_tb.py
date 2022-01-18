from amaranth import *
from ds_fsm import DS_FSM

class DS_FSM_TB(Elaboratable):
    def __init__(self, endA_srcfreq, endB_srcfreq, txfreq):
        #######################################################
        # END A
        #######################################################
        self.i_endA_reset = Signal()
        self.i_endA_link_disabled = Signal()
        self.i_endA_link_start = Signal()
        self.i_endA_autostart = Signal()
        self.i_endA_tick = Signal()
        self.o_endA_tick = Signal()
        self.o_endA_time_flags = Signal(2)
        self.o_endA_time = Signal(6)
        self.o_endA_link_error = Signal()
        self.o_endA_tx_ready = Signal()
        # FIFO RX
        self.i_endA_r_en = Signal()
        self.o_endA_r_data = Signal(8)
        self.o_endA_r_rdy = Signal()
        # FIFO TX
        self.i_endA_w_en = Signal()
        self.i_endA_w_data = Signal(8)
        self.o_endA_w_rdy = Signal()
        #######################################################

        #######################################################
        # END B
        #######################################################
        self.i_endB_reset = Signal()
        self.i_endB_link_disabled = Signal()
        self.i_endB_link_start = Signal()
        self.i_endB_autostart = Signal()
        self.i_endB_tick = Signal()
        self.o_endB_tick = Signal()
        self.o_endB_time_flags = Signal(2)
        self.o_endB_time = Signal(6)
        self.o_endB_link_error = Signal()
        self.o_endB_tx_ready = Signal()
        # FIFO RX
        self.i_endB_r_en = Signal()
        self.o_endB_r_data = Signal(8)
        self.o_endB_r_rdy = Signal()
        # FIFO TX
        self.i_endB_w_en = Signal()
        self.i_endB_w_data = Signal(8)
        self.o_endB_w_rdy = Signal()
        #######################################################

        self._endA_srcfreq = endA_srcfreq
        self._endB_srcfreq = endB_srcfreq
        self._txfreq = txfreq

    def elaborate(self, platform):
        tb = Module()

        tb.submodules.endA = endA = DS_FSM(self._endA_srcfreq, self._txfreq, True)
        tb.submodules.endB = endB = DS_FSM(self._endB_srcfreq, self._txfreq, False)

        tb.d.comb += [
            #######################################################
            # END A
            #######################################################
            endA.i_d.eq(endB.o_d),
            endA.i_s.eq(endB.o_s),
            endA.i_reset.eq(self.i_endA_reset),
            endA.i_link_disabled.eq(self.i_endA_link_disabled),
            endA.i_link_start.eq(self.i_endA_link_start),
            endA.i_autostart.eq(self.i_endA_autostart),
            endA.i_tick.eq(self.i_endA_tick),
            self.o_endA_tick.eq(endA.o_tick),
            self.o_endA_time_flags.eq(endA.o_time_flags),
            self.o_endA_time.eq(endA.o_time),
            self.o_endA_link_error.eq(endA.o_link_error),
            self.o_endA_tx_ready.eq(endA.o_tx_ready),
            # FIFO RX
            endA.i_r_en.eq(self.i_endA_r_en),
            self.o_endA_r_data.eq(endA.o_r_data),
            self.o_endA_r_rdy.eq(endA.o_r_rdy),
            # FIFO TX
            endA.i_w_en.eq(self.i_endA_w_en),
            endA.i_w_data.eq(self.i_endA_w_data),
            self.o_endA_w_rdy.eq(endA.o_w_rdy),
            #######################################################

            #######################################################
            # END B
            #######################################################
            endB.i_d.eq(endA.o_d),
            endB.i_s.eq(endA.o_s),
            endB.i_reset.eq(self.i_endB_reset),
            endB.i_link_disabled.eq(self.i_endB_link_disabled),
            endB.i_link_start.eq(self.i_endB_link_start),
            endB.i_autostart.eq(self.i_endB_autostart),
            endB.i_tick.eq(self.i_endB_tick),
            self.o_endB_tick.eq(endB.o_tick),
            self.o_endB_time_flags.eq(endB.o_time_flags),
            self.o_endB_time.eq(endB.o_time),
            self.o_endB_link_error.eq(endB.o_link_error),
            self.o_endB_tx_ready.eq(endB.o_tx_ready),
            # FIFO RX
            endB.i_r_en.eq(self.i_endB_r_en),
            self.o_endB_r_data.eq(endB.o_r_data),
            self.o_endB_r_rdy.eq(endB.o_r_rdy),
            # FIFO TX
            endB.i_w_en.eq(self.i_endB_w_en),
            endB.i_w_data.eq(self.i_endB_w_data),
            self.o_endB_w_rdy.eq(endB.o_w_rdy)
            #######################################################
        ]

        return tb

    def ports(self):
        return [
            self.i_endA_reset, self.i_endA_link_disabled,
            self.i_endA_link_start, self.i_endA_autostart, self.i_endA_tick,
            self.o_endA_tick, self.o_endA_time_flags, self.o_endA_time,
            self.o_endA_link_error, self.o_endA_tx_ready, self.i_endA_r_en,
            self.o_endA_r_data, self.o_endA_r_rdy, self.i_endA_w_en,
            self.i_endA_w_data, self.o_endA_w_rdy, self.i_endB_reset,
            self.i_endB_link_disabled, self.i_endB_link_start,
            self.i_endB_autostart, self.i_endB_tick, self.o_endB_tick,
            self.o_endB_time_flags, self.o_endB_time, self.o_endB_link_error,
            self.o_endB_tx_ready, self.i_endB_r_en, self.o_endB_r_data,
            self.o_endB_r_rdy, self.i_endB_w_en, self.i_endB_w_data,
            self.o_endB_w_rdy
        ]