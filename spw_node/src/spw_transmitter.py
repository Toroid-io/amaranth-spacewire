from nmigen import *
from nmigen.sim import Simulator, Delay
from .ds_shift_registers import DSOutputCharSR
from .ds_encoder import DSEncoder
from .clock_divider import ClockDivider
from bitarray import bitarray
from nmigen_boards.de0_nano import DE0NanoPlatform


class SpWTransmitter(Elaboratable):
    def __init__(self, srcfreq, txfreq):
        self.i_reset = Signal()
        self.i_char = Signal(8)
        self.i_send_char = Signal()
        self.i_send_fct = Signal()
        self.i_send_esc = Signal()
        self.i_send_eop = Signal()
        self.i_send_eep = Signal()
        self.i_send_time = Signal()
        self.o_ready = Signal()
        self.o_d = Signal()
        self.o_s = Signal()
        self._txfreq = txfreq
        self._srcfreq = srcfreq

    def elaborate(self, elaborate):
        m = Module()

        m.submodules.tr_clk = tr_clk = ClockDivider(self._srcfreq, self._txfreq)
        m.domains.tx = ClockDomain("tx", local=True)
        m.d.comb += ClockSignal("tx").eq(tr_clk.o)
        m.submodules.encoder = encoder = DomainRenamer("tx")(DSEncoder())
        m.submodules.sr = sr = DomainRenamer("tx")(DSOutputCharSR())

        char_fct = Signal(8, reset=0b00000000)
        char_esc = Signal(8, reset=0b00000011)
        char_eop = Signal(8, reset=0b00000010)
        char_eep = Signal(8, reset=0b00000001)
        parity_control = Signal()
        parity_data = Signal()
        # One tx clock delay to hold d/s signals at reset
        encoder_reset = Signal(reset=1)
        # Reset 2 is needed because shift register outputs the data to the
        # encoder one-clock late
        encoder_reset_2 = Signal(reset=1)
        send_null = Signal()

        m.d.comb += [
            encoder.i_d.eq(sr.o_output),
            encoder.i_reset.eq(encoder_reset_2),
            sr.i_reset.eq(self.i_reset),
            self.o_d.eq(encoder.o_d),
            self.o_s.eq(encoder.o_s)
        ]

        m.d.tx += encoder_reset.eq(self.i_reset)
        m.d.tx += encoder_reset_2.eq(encoder_reset)

        with m.FSM() as tr_fsm:
            with m.State("Wait"):
                with m.If(sr.o_ready == 1):
                    with m.If(self.i_send_char == 1):
                        m.d.sync += [
                            sr.i_send_data.eq(1),
                            sr.i_input.eq(self.i_char)
                        ]
                        m.next = "WaitTxStartData"
                    with m.Elif(self.i_send_esc == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_esc)
                        ]
                        m.next = "WaitTxStartControl"
                    with m.Elif(self.i_send_fct == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_fct)
                        ]
                        m.next = "WaitTxStartControl"
                    with m.Elif(self.i_send_eop == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_eop)
                        ]
                        m.next = "WaitTxStartControl"
                    with m.Elif(self.i_send_eep == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_eep)
                        ]
                        m.next = "WaitTxStartControl"
                    with m.Elif(self.i_send_time == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_esc)
                        ]
                        m.next = "SendTimeA"
                    with m.Elif(send_null == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_esc)
                        ]
                        m.next = "SendNullA"
            with m.State("SendNullA"):
                with m.If(sr.o_ready == 0):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = "SendNullB"
            with m.State("SendNullB"):
                with m.If(sr.o_ready == 1):
                    m.d.sync += [
                        sr.i_send_control.eq(1),
                        sr.i_input.eq(char_fct)
                    ]
                    m.next = "SendNullC"
            with m.State("SendNullC"):
                with m.If(sr.o_ready == 0):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = "Wait"
            with m.State("WaitTxStartControl"):
                with m.If(sr.o_ready == 0):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = "Wait"
            with m.State("WaitTxStartData"):
                with m.If(sr.o_ready == 0):
                    m.d.sync += sr.i_send_data.eq(0)
                    m.next = "Wait"
            with m.State("SendTimeA"):
                with m.If(sr.o_ready == 0):
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                    ]
                    m.next = "SendTimeB"
            with m.State("SendTimeB"):
                with m.If(sr.o_ready == 1):
                    m.d.sync += [
                        sr.i_send_data.eq(1),
                        sr.i_input.eq(self.i_char)
                    ]
                    m.next = "SendTimeC"
            with m.State("SendTimeC"):
                with m.If(sr.o_ready == 0):
                    m.d.sync += [
                        sr.i_send_data.eq(0)
                    ]
                    m.next = "Wait"

            m.d.comb += self.o_ready.eq(tr_fsm.ongoing("Wait") & (sr.o_ready == 1))
            m.d.sync += send_null.eq(~self.i_send_char & ~self.i_send_eep & ~self.i_send_eop & ~self.i_send_esc & ~self.i_send_fct & self.o_ready)

        return m

    def ports(self):
        return [
            self.i_char, self.i_reset, self.i_send_eep, self.i_send_eop,
            self.i_send_fct, self.i_send_esc, self.i_send_char
        ]

if __name__ == '__main__':
    i_char = Signal(8)
    i_reset = Signal(reset=1)
    i_send_char = Signal()
    i_send_eep = Signal()
    i_send_eop = Signal()
    i_send_fct = Signal()
    m = Module()
    m.submodules.tr = tr = SpWTransmitter(1e6, 0.25e6)
    m.d.comb += [
        tr.i_char.eq(i_char),
        tr.i_reset.eq(i_reset),
        tr.i_send_char.eq(i_send_char),
        tr.i_send_eep.eq(i_send_eep),
        tr.i_send_eop.eq(i_send_eop),
        tr.i_send_fct.eq(i_send_fct)
    ]

    sim = Simulator(m)
    sim.add_clock(1e-6)

    def char_to_bits(c):
        ret = bitarray(endian='little')
        ret.frombytes(c.encode())
        return ret

    def test():
        for _ in range(50):
            yield
        yield i_reset.eq(0)
        for _ in range(150):
            yield
        while (yield tr.o_ready == 1):
            yield
        while (yield tr.o_ready == 0):
            yield
        yield i_char.eq(ord('A'))
        yield i_send_char.eq(1)
        while (yield tr.o_ready == 1):
            yield
        yield i_send_char.eq(0)
        while (yield tr.o_ready == 0):
            yield
        yield i_send_eep.eq(1)
        while (yield tr.o_ready == 1):
            yield
        yield i_send_eep.eq(0)
        while (yield tr.o_ready == 0):
            yield
        for _ in range(150):
            yield

    sim.add_sync_process(test)
    with sim.write_vcd("vcd/spw_transmitter.vcd", "gtkw/spw_transmitter.gtkw", traces=tr.ports()):
        sim.run()

    pl = DE0NanoPlatform()
    class TOP(Elaboratable):
        def __init__(self, linkfreq):
            self._linkfreq = linkfreq

        def elaborate(self, pl):
            m = Module()
            m.submodules.tr = tr = SpWTransmitter(pl.default_clk_frequency, self._linkfreq)
            m.d.comb += [
                tr.i_reset.eq(0),
                tr.i_char.eq(0),
                tr.i_send_char.eq(0),
                tr.i_send_fct.eq(0),
                tr.i_send_esc.eq(0),
                tr.i_send_eop.eq(0),
                tr.i_send_eep.eq(0),
                tr.i_send_time.eq(0),
                pl.request('led', 0).eq(tr.o_d),
                pl.request('led', 1).eq(tr.o_s),
                pl.request('led', 2).eq(tr.o_ready)
            ]
            return m

    DE0NanoPlatform().build(TOP(1), do_program=True)