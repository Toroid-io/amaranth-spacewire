from amaranth import *
from amaranth.sim import Simulator
from ..misc.spw_delay import SpWDelay


class SpWDisconnectDetector(Elaboratable):
    """Watch out for link disconnections.

    Update a SpaceWire delay countdown every time a new bit is received, so that
    we can detect a link disconnect.

    Parameters:
    ----------
    srcfreq : int
        The main core frequency in Hz.
    disconnect_delay : int
        The disconnect delay in seconds.

    Attributes
    ----------
    i_reset : Signal(1), in
        Reset signal.
    i_store_en : Signal(1), in
        Indication that a bit was received.
    o_disconnected : Signal(1), out
        Indication that the ``disconnect_delay`` has elapsed without
        ``i_store_en`` being asserted.
    """
    def __init__(self, srcfreq, disconnect_delay=850e-9):
        self.i_reset = Signal()
        self.i_store_en = Signal()
        self.o_disconnected = Signal()

        self._srcfreq = srcfreq
        self._disconnect_delay = disconnect_delay

    def elaborate(self, platform):
        m = Module()

        m.submodules.delay = delay = SpWDelay(self._srcfreq, self._disconnect_delay, strategy='at_most')

        m.d.comb += [
            self.o_disconnected.eq(delay.o_elapsed)
        ]

        with m.FSM() as fsm:
            with m.State("INIT"):
                with m.If(~self.i_reset & self.i_store_en):
                    m.d.comb += delay.i_start.eq(1)
                    m.next = "RUN"
                with m.Else():
                    m.d.comb += delay.i_start.eq(0)
            with m.State("RUN"):
                with m.If(self.i_reset):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = "INIT"
                with m.Elif(self.i_store_en):
                    m.d.comb += delay.i_start.eq(0)
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

        return m

    def ports(self):
        return [self.i_reset, self.i_store_en, self.o_disconnected]
