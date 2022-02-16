from amaranth import *
from amaranth.sim import Simulator


class PulseGenerator(Elaboratable):
    """Outputs a single pulse in the clock domain when input is asserted.

    Attributes
    ----------
    i_en : Signal(1), in
        Input signal.
    i_reset : Signal(1), in
        Reset signal to hold the pulse output low.
    o_pulse : Signal(1), out
        Output pulse.
    """
    def __init__(self):
        self.i_en = Signal()
        self.i_reset = Signal()
        self.o_pulse = Signal()

    def elaborate(self, platform):
        m = Module()

        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(~self.i_reset & self.i_en):
                    m.d.sync += self.o_pulse.eq(1)
                    m.next = "PULSE"
            with m.State("PULSE"):
                m.d.sync += self.o_pulse.eq(0)
                with m.If(self.i_reset | ~self.i_en):
                    m.next = "IDLE"

        return m

    def ports(self):
        return [self.i_en, self.o_pulse]
