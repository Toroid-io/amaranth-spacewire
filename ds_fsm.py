from nmigen import *
from nmigen.lib.fifo import SyncFIFOBuffered
from nmigen.sim import Simulator
from bitarray import bitarray
from ds_transmitter import DSTransmitter
from ds_receiver import DSReceiver
from ds_delay import DSDelay


class DS_FSM(Elaboratable):
    def __init__(self, srcfreq, txfreq):
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
        m.submodules.rx = rx = DSReceiver()
        m.submodules.delay = delay = DSDelay(self._srcfreq, 12.8e-6, strategy='at_least')

        tx_reset = Signal(reset=1)
        tx_can_send_char = Signal()
        tx_can_send_fct = Signal()
        rx_reset = Signal(reset=1)
        rx_tokens_count = Signal(range(2 + 1), reset=2) # TODO range rx fifo size / 8
        rx_read_counter = Signal(range(8))
        tx_credit = Signal(range(16 + 1)) # TODO tx fifo size
        read_in_progress = Signal()

        m.d.comb += [
            tr.i_reset.eq(tx_reset),
            self.o_d.eq(tr.o_d),
            self.o_s.eq(tr.o_s),
            rx.i_reset.eq(rx_reset),
            rx.i_d.eq(tr.o_d),
            rx.i_s.eq(tr.o_s),
            tx_can_send_fct.eq((rx_tokens_count > 0) & ((tr.o_ready & ~tr.i_send_fct) == 1))
        ]

        m.submodules.rx_fifo = rx_fifo = SyncFIFOBuffered(width=8, depth=16)
        m.submodules.tx_fifo = tx_fifo = SyncFIFOBuffered(width=8, depth=16)

        m.d.comb += [
            rx_fifo.r_en.eq(self.i_r_en),
            self.o_r_data.eq(rx_fifo.r_data),
            self.o_r_rdy.eq(rx_fifo.r_rdy),

            tx_fifo.w_en.eq(self.i_w_en),
            tx_fifo.w_data.eq(self.i_w_data),
            self.o_w_rdy.eq(tx_fifo.w_rdy),

            tr.i_char.eq(tx_fifo.r_data),
            tx_can_send_char.eq((tx_fifo.level > 0) & tr.o_ready & ~tx_fifo.r_en & (tx_credit > 0)),
            read_in_progress.eq(self.i_r_en & rx_fifo.r_rdy)
        ]

        with m.FSM() as main_fsm:
            with m.State("ErrorReset"):
                m.d.comb += delay.i_start.eq(1)
                m.d.sync += rx_reset.eq(0)
                m.next = "ErrorResetDelay"
            with m.State("ErrorResetDelay"):
                with m.If(delay.o_half_elapsed):
                    m.d.comb += [
                        delay.i_reset.eq(1)
                    ]
                    m.next = "ErrorWait"
            with m.State("ErrorWait"):
                m.d.comb += [
                    delay.i_start.eq(1)
                ]
                m.next = "ErrorWaitDelay"
            with m.State("ErrorWaitDelay"):
                with m.If(delay.o_elapsed == 1):
                    m.next = "Ready"
            with m.State("Ready"):
                with m.If(self.i_link_enable == 1):
                    m.d.sync += [
                        tx_reset.eq(0)
                    ]
                    m.next = "Started"
            with m.State("Started"):
                with m.If(rx.o_got_null == 1):
                    m.next = "Connecting"
            with m.State("Connecting"):
                with m.If(tx_can_send_fct):
                    m.d.sync += tr.i_send_fct.eq(1)
                with m.Else():
                    m.d.sync += tr.i_send_fct.eq(0)

                with m.If((rx.o_got_fct & ~rx.o_got_null) == 1):
                    m.d.sync += tx_credit.eq(tx_credit + 8)
                    m.next = "Run"
            with m.State("Run"):
                # TX
                with m.If(tx_can_send_fct):
                    m.d.sync += tr.i_send_fct.eq(1)
                with m.Elif(tx_can_send_char):
                    m.d.sync += [
                        tr.i_send_char.eq(1),
                        tx_fifo.r_en.eq(1)
                    ]
                with m.Else():
                    m.d.sync += [
                        tr.i_send_char.eq(0),
                        tr.i_send_fct.eq(0),
                        tx_fifo.r_en.eq(0)
                    ]

                #RX
                with m.If(rx.o_got_data & ~rx_fifo.w_en):
                    m.d.sync += [
                        rx_fifo.w_en.eq(1),
                        rx_fifo.w_data.eq(rx.o_data_char)
                    ]
                with m.Else():
                    m.d.sync += [
                        rx_fifo.w_en.eq(0)
                    ]

        # Tokens and credit management
        with m.If(main_fsm.ongoing("Connecting") | main_fsm.ongoing("Run")):
            with m.If(tx_can_send_char & ~rx.o_got_fct):
                m.d.sync += tx_credit.eq(tx_credit - 1)
            with m.If(rx.o_got_fct & ~rx.o_got_null & ~tx_can_send_char):
                m.d.sync += tx_credit.eq(tx_credit + 8)
            with m.Elif(rx.o_got_fct & ~rx.o_got_null & tx_can_send_char):
                m.d.sync += tx_credit.eq(tx_credit + 7)

            with m.If(read_in_progress):
                m.d.sync += rx_read_counter.eq(rx_read_counter + 1)

            with m.If(read_in_progress & ~tx_can_send_fct):
                with m.If(rx_read_counter == 7):
                    m.d.sync += rx_tokens_count.eq(rx_tokens_count + 1)
            with m.Elif(~read_in_progress & tx_can_send_fct):
                m.d.sync += rx_tokens_count.eq(rx_tokens_count - 1)
            with m.If(read_in_progress & tx_can_send_fct):
                with m.If(~(rx_read_counter == 7)):
                    m.d.sync += rx_tokens_count.eq(rx_tokens_count - 1)

        return m

    def ports(self):
        return [self.i_link_enable, self.o_d, self.o_s]


if __name__ == '__main__':
    srcfreq = 5e6
    linkfreq = 0.25e6
    i_link_enable = Signal()
    m = Module()
    m.submodules.fsm = fsm = DS_FSM(srcfreq, linkfreq)
    m.d.comb += [
        fsm.i_link_enable.eq(i_link_enable)
    ]

    sim = Simulator(m)
    sim.add_clock(1/srcfreq)

    def char_to_bits(c):
        ret = bitarray(endian='little')
        ret.frombytes(c.encode())
        return ret

    def test():
        #yield i_char.eq(ord('A'))
        for _ in range(150):
            yield
        yield i_link_enable.eq(1)
        for _ in range(1200):
            yield
        for i in range(18):
            yield fsm.i_w_en.eq(1)
            yield fsm.i_w_data.eq(ord('A')+i)
            yield
        yield fsm.i_w_en.eq(0)
        for _ in range(10000):
            yield

    def read_from_fifo():
        for _ in range(5000):
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