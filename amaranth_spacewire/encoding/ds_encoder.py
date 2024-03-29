from amaranth import *
from amaranth.utils import bits_for


class DSEncoder(Elaboratable):
    def __init__(self):
        self.i_reset = Signal()
        self.i_en = Signal()
        self.i_d = Signal()
        self.o_d = Signal()
        self.o_s = Signal()
        self.o_ready = Signal()

    def elaborate(self, platform):
        m = Module()

        with m.FSM() as encoder_fsm:
            with m.State("RESET"):
                with m.If(~self.i_reset):
                    m.next = "NORMAL"
            with m.State("NORMAL"):
                with m.If(self.i_reset):
                    m.d.sync += self.o_s.eq(0)
                    m.next = "RESET_D"
                with m.Elif(self.i_en):
                    with m.If(~(self.o_d ^ self.i_d)):
                        m.d.sync += self.o_s.eq(~self.o_s)
                    m.d.sync += self.o_d.eq(self.i_d)
            with m.State("RESET_D"):
                m.d.sync += self.o_d.eq(0)
                with m.If(self.i_reset):
                    m.next = "RESET"
                with m.Else():
                    m.next = "NORMAL"

        m.d.sync += self.o_ready.eq(encoder_fsm.ongoing("NORMAL") & ~self.i_reset)

        return m

    def ports(self):
        return [self.i_d, self.o_d, self.o_s]
