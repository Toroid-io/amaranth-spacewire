from amaranth import *
from amaranth.sim import Simulator
from amaranth.lib.cdc import FFSynchronizer
from .clock_divider import ClockDivider

#https://vlsitutorials.com/glitch-free-clock-mux/

class ClockMux(Elaboratable):
    """A glitch-free, two-input clock multiplexer.

    Parameters:
    ----------
    stages : int
        The number of stages in the internal logic. Adds latency when switching
        clocks.

    Attributes
    ----------
    i_clk_a : Signal(1), in
        Input clock A
    i_clk_b : Signal(1), in
        Input clock B
    i_sel : Signal(1), in
        Clock selection. `0` selects ``i_clk_a`` and `1` selects ``i_clk_b``.
    o_clk : Signal(1), out
        Output clock signal, based on ``i_sel``.
    """
    def __init__(self, stages=3):
        self.i_clk_a = Signal()
        self.i_clk_b = Signal()
        self.i_sel = Signal()
        self.o_clk = Signal()
        self._stages = stages

    def elaborate(self, platform):
        m = Module()

        and_1 = Signal()
        and_1_reg = Signal()
        and_1_out = Signal()
        and_2 = Signal()
        and_2_reg = Signal()
        and_2_out = Signal()

        m.domains += ClockDomain("clk_a", local=True)
        m.domains += ClockDomain("clk_b", local=True)

        m.submodules += FFSynchronizer(and_1, and_1_reg, reset=0, o_domain="clk_a", stages=self._stages)
        m.submodules += FFSynchronizer(and_2, and_2_reg, reset=0, o_domain="clk_b", stages=self._stages)

        m.d.comb += [
            ClockSignal("clk_a").eq(self.i_clk_a),
            ClockSignal("clk_b").eq(self.i_clk_b)
        ]

        m.d.comb += [
            and_1.eq(~self.i_sel & ~and_2_reg),
            and_2.eq(self.i_sel & ~and_1_reg),
            and_1_out.eq(and_1_reg & ClockSignal("clk_a")),
            and_2_out.eq(and_2_reg & ClockSignal("clk_b")),
            self.o_clk.eq(and_1_out | and_2_out)
        ]

        return m

    def ports(self):
        return [self.i_sel, self.o_clk]
