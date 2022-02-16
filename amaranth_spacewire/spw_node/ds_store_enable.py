from amaranth import *
from amaranth.sim import Simulator, Delay
from .pulse_generator import PulseGenerator
from .ds_decoder import DSDecoder


class DSStoreEnable(Elaboratable):
    """Outputs a pulse every time an edge is detected in the input DDR clock.

    The output pulse is always first asserted on a rising edge on the input DDR
    clock.

    Attributes
    ----------
    i_d : Signal(1), in
        Data signal from the Data/Strobe pair.
    i_s : Signal(1), in
        Strobe signal from the Data/Strobe pair.
    o_d : Signal(1), out
        Data signal from the output Data/Clock pair. The changes of this signal are in
        sync with the DDR change in ``o_clk_ddr``.
    o_clk_ddr : Signal(1), out
        DDR Clock from the output Data/Clock pair. Associated with changes in
        ``o_d``.
    """
    def __init__(self):
        self.i_reset = Signal()
        self.i_d = Signal()
        self.i_clk_ddr = Signal()
        self.o_d = Signal()
        self.o_store_en = Signal()

    def elaborate(self, platform):
        # Copy (comb) of the input DDR clock
        internal_clk_ddr = Signal()
        # Negated copy (comb) of the input DDR clock
        internal_clk_ddr_n = Signal()
        # Output pulse from a PulseGenerator, rising edge of the DDR clock
        pulse_rising = Signal()
        # Output pulse from a PulseGenerator, falling edge of the DDR clock
        pulse_falling = Signal()
        # This is a safeguard to avoid asserting the ``o_store_en`` signal
        # before a rising edge was detected
        got_first_transition = Signal()

        m = Module()

        pg_rising = PulseGenerator()
        pg_falling = PulseGenerator()
        m.submodules += [pg_rising, pg_falling]

        m.d.comb += [
            pg_rising.i_en.eq(internal_clk_ddr),
            pg_rising.i_reset.eq(self.i_reset),
            pulse_rising.eq(pg_rising.o_pulse),

            # Do not produce a falling-edge pulse before a rising-edge one
            pg_falling.i_en.eq(internal_clk_ddr_n & got_first_transition),
            pg_falling.i_reset.eq(self.i_reset),
            pulse_falling.eq(pg_falling.o_pulse)
        ]

        with m.If(self.i_reset):
            m.d.comb += [
                internal_clk_ddr.eq(0),
                internal_clk_ddr_n.eq(0)
            ]
            m.d.sync += [
                self.o_store_en.eq(0),
                got_first_transition.eq(0)
            ]
        with m.Else():
            m.d.comb += [
                internal_clk_ddr.eq(self.i_clk_ddr),
                internal_clk_ddr_n.eq(~self.i_clk_ddr)
            ]
            m.d.sync += [
                self.o_store_en.eq(pulse_rising | pulse_falling),
                self.o_d.eq(self.i_d)
            ]

            with m.If(pulse_rising & ~got_first_transition):
                m.d.sync += got_first_transition.eq(1)

        return m

    def ports(self):
        return [self.i_reset, self.i_d, self.i_clk_ddr, self.o_d, self.o_store_en]
