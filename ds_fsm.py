from nmigen import *
from nmigen.lib.fifo import SyncFIFOBuffered
from nmigen.sim import Simulator
from ds_transmitter import DSTransmitter
from ds_receiver import DSReceiver
from ds_delay import DSDelay
from ds_sim_utils import *

class DS_FSM(Elaboratable):
    def __init__(self, srcfreq, txfreq):
        self.i_reset = Signal()
        self.i_link_enable = Signal()
        self.o_tx_ready = Signal()
        self.o_d = Signal()
        self.o_s = Signal()

        # FIFO
        self.i_r_en = Signal()
        self.o_r_data = Signal(8)
        self.o_r_rdy = Signal()
        self.i_w_en = Signal()
        self.i_w_data = Signal(8)
        self.o_w_rdy = Signal()

        self._srcfreq = srcfreq
        self._txfreq = txfreq
        pass

    def elaborate(self, platform):
        m = Module()

        m.submodules.tr = tr = DSTransmitter(self._srcfreq, self._txfreq)
        m.submodules.rx = rx = DSReceiver(self._srcfreq)
        m.submodules.delay = delay = DSDelay(self._srcfreq, 12.8e-6, strategy='at_least')

        tr_pre_send = Signal()
        rx_error = Signal()
        rx_tokens_count = Signal(range(2 + 1), reset=2) # TODO range rx fifo size / 8
        rx_read_counter = Signal(range(8))
        tx_credit = Signal(range(16 + 1)) # TODO tx fifo size
        read_in_progress = Signal()
        gotNULL = Signal()

        m.d.comb += [
            self.o_d.eq(tr.o_d),
            self.o_s.eq(tr.o_s),
            rx.i_d.eq(tr.o_d),
            rx.i_s.eq(tr.o_s),
            rx_error.eq(rx.o_escape_error | rx.o_parity_error | rx.o_read_error | rx.o_disconnect_error)
        ]

        m.submodules.rx_fifo = rx_fifo = SyncFIFOBuffered(width=8, depth=16)
        m.submodules.tx_fifo = tx_fifo = SyncFIFOBuffered(width=8, depth=16)

        m.d.comb += [
            rx_fifo.r_en.eq(self.i_r_en),
            self.o_r_data.eq(rx_fifo.r_data),
            self.o_r_rdy.eq(rx_fifo.r_rdy),
            rx_fifo.w_data.eq(rx.o_data_char),

            tx_fifo.w_en.eq(self.i_w_en),
            tx_fifo.w_data.eq(self.i_w_data),
            self.o_w_rdy.eq(tx_fifo.w_rdy),

            tr.i_char.eq(tx_fifo.r_data),
            read_in_progress.eq(self.i_r_en & rx_fifo.r_rdy)
        ]

        m.d.sync += [
            tr.i_send_eop.eq(0),
            tr.i_send_eep.eq(0),
            tr.i_send_esc.eq(0)
        ]

        with m.FSM() as main_fsm:
            with m.State("ErrorReset"):
                m.d.comb += rx.i_reset.eq(1)
                m.d.comb += tr.i_reset.eq(1)

                with m.If(self.i_reset):
                    pass
                with m.Elif(delay.o_half_elapsed):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = "ErrorWait"
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State("ErrorWait"):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(1)

                with m.If((rx_error | rx.o_got_fct | rx.o_got_data) == 1): # TODO: Missing o_got_time_code
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = "ErrorReset"
                with m.Elif(delay.o_elapsed == 1):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = "Ready"
                with m.Elif(rx.o_got_null):
                    m.d.sync += gotNULL.eq(1)
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State("Ready"):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(1)

                with m.If((rx_error | rx.o_got_fct | rx.o_got_data) == 1): # TODO: Missing o_got_time_code
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = "ErrorReset"
                with m.Elif(self.i_link_enable == 1):
                    m.next = "Started"
                with m.Elif(rx.o_got_null):
                    m.d.sync += gotNULL.eq(1)
            with m.State("Started"):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(0)

                with m.If((rx_error | rx.o_got_fct | rx.o_got_data | delay.o_elapsed) == 1): # TODO: Missing o_got_time_code
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = "ErrorReset"
                with m.Elif((gotNULL | rx.o_got_null) == 1):
                    m.d.sync += gotNULL.eq(1)
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = "Connecting"
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State("Connecting"):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(0)

                with m.If((rx_error | rx.o_got_data | delay.o_elapsed) == 1): # TODO: Missing o_got_time_code
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = "ErrorReset"
                with m.Elif(rx.o_got_fct == 1):
                    m.d.sync += tx_credit.eq(tx_credit + 8)
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = "Run"
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State("Run"):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(0)
                m.d.comb += tr_pre_send.eq((tx_fifo.level > 0) & tr.o_ready & (tx_credit > 0) & tx_fifo.r_rdy)

                with m.If((rx_error | ~self.i_link_enable) == 1): # TODO: Missing credit error
                    m.d.comb += delay.i_reset.eq(1)
                    # TODO Reset tokens and credits
                    m.next = "ErrorReset"
                with m.Else():
                    # TX: i_send_char shifted a cycle to allow tx_fifo to output its value
                    m.d.comb += tx_fifo.r_en.eq(tr_pre_send)
                    m.d.comb += tr.i_send_char.eq(tr_pre_send)
                    m.d.comb += rx_fifo.w_en.eq(rx.o_got_data)

        # Tokens and credit management
        with m.If(main_fsm.ongoing("Connecting") | main_fsm.ongoing("Run")):
            m.d.comb += tr.i_send_fct.eq((rx_tokens_count > 0) & (tr.o_ready == 1))

            with m.If(tr.i_send_char & ~rx.o_got_fct):
                m.d.sync += tx_credit.eq(tx_credit - 1)
            with m.If(rx.o_got_fct & ~tr.i_send_char):
                m.d.sync += tx_credit.eq(tx_credit + 8)
            with m.Elif(rx.o_got_fct & tr.i_send_char):
                m.d.sync += tx_credit.eq(tx_credit + 7)

            with m.If(read_in_progress):
                m.d.sync += rx_read_counter.eq(rx_read_counter + 1)

            with m.If(read_in_progress & ~tr.i_send_fct):
                with m.If(rx_read_counter == 7):
                    m.d.sync += rx_tokens_count.eq(rx_tokens_count + 1)
            with m.Elif(~read_in_progress & tr.i_send_fct):
                m.d.sync += rx_tokens_count.eq(rx_tokens_count - 1)
            with m.If(read_in_progress & tr.i_send_fct):
                with m.If(~(rx_read_counter == 7)):
                    m.d.sync += rx_tokens_count.eq(rx_tokens_count - 1)

        return m

    def ports(self):
        return [self.i_link_enable, self.o_d, self.o_s]


if __name__ == '__main__':
    srcfreq = 50e6
    linkfreq = 45e6
    i_link_enable = Signal()
    m = Module()
    m.submodules.fsm = fsm = DS_FSM(srcfreq, linkfreq)
    m.d.comb += [
        fsm.i_link_enable.eq(i_link_enable)
    ]

    sim = Simulator(m)
    sim.add_clock(1/srcfreq)

    def test():
        for _ in range(ds_sim_period_to_ticks(25e-6, srcfreq)):
            yield
        yield i_link_enable.eq(1)
        for _ in range(ds_sim_period_to_ticks(30e-6, srcfreq)):
            yield
        for i in range(40):
            yield fsm.i_w_en.eq(1)
            yield fsm.i_w_data.eq(ord('A')+i)
            yield
        yield fsm.i_w_en.eq(0)
        for _ in range(ds_sim_period_to_ticks(100e-6, srcfreq)):
            yield

    def read_from_fifo():
        for _ in range(ds_sim_period_to_ticks(400e-6, srcfreq)):
            yield
        while True:
            if (yield fsm.o_r_rdy):
                yield fsm.i_r_en.eq(1)
            else:
                yield fsm.i_r_en.eq(0)
            yield



    sim.add_sync_process(test)
    sim.add_sync_process(read_from_fifo)
    with sim.write_vcd("ds_fsm.vcd", "ds_fsm.gtkw", traces=fsm.ports()):
        sim.run_until(1200e-6)