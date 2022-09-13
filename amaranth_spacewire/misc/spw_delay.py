from amaranth import *
from amaranth.utils import bits_for
from amaranth.sim import Simulator, Delay
import math

def _ticksForDelay(freq, delay, max_ppm=None, strategy='at_most'):
    """Adapted from a clock divider found on the Glasgow board gateware.
    """
    period = 1/freq
    if strategy == 'at_most':
        ticks = math.floor(delay/period)
    else:
        ticks = math.ceil(delay/period)

    ppm = 1000000 * ((period * ticks) - delay) / delay

    if max_ppm is not None and ppm > max_ppm:
        raise ArgumentError("Ticks deviation is too high")

    if delay == 0 or delay is None or ticks == 0:
        raise ArgumentError("Frequency is too low for the requested delay")

    return ticks

class SpWDelay(Elaboratable):
    """Countdown for the two delays in SpaceWire state machine.

    Two indications are output from this module, a half-elapsed indication and a
    full-elapsed indication. This would normally match the 6.4 us and 12.8 us
    delays, but can be customized for specific needs.

    Parameters:
    ----------
    srcfreq : int
        The main core frequency used to compute the countdown register size, in
        Hz.
    delay : int
        The full delay period. For example, 12.8e-6 for the standard SpaceWire
        delay.
    strategy : {'at_least', 'at_most'}
        The strategy to use when rounding the register values: ``at_most`` will
        generate a delay of no more than ``delay`` seconds, guaranteeing the
        upper limit; ``at_least`` will generate a delay of at least ``delay``
        seconds, even if that means to generate a bit longer delay.

    Attributes
    ----------
    i_start : Signal(1), in
        Indication that the countdown should start. Once started, it is ignored
        until the delay has elapsed, or ``i_reset`` is asserted.
    o_half_elapsed : Signal(1), out
        Half-time elapsed indication.
    o_elapsed : Signal(1), out
        Full-time elapsed indication.
    """
    def __init__(self, srcfreq, delay, strategy='at_least'):
        self.i_start = Signal()
        self.o_half_elapsed = Signal()
        self.o_elapsed = Signal()
        ticks = _ticksForDelay(srcfreq, delay, strategy=strategy)
        self._strategy = strategy

        self._counter = Signal(bits_for(ticks))

        if self._strategy == 'at_least':
            self._counter_half = math.ceil(ticks/2)
            self._counter_max = ticks
        else:
            # Count one less cycle because the user will react one cycle later
            self._counter_half = math.floor(ticks/2) - 1
            self._counter_max = ticks - 1

    def elaborate(self, platform):
        m = Module()

        with m.If(~self.i_start):
            m.d.sync += self._counter.eq(0)
        with m.Else():
            m.d.sync += self._counter.eq(self._counter + 1)

        with m.If(~self.i_start):
            m.d.sync += [self.o_elapsed.eq(0), self.o_half_elapsed.eq(0)]
        with m.Elif(self._counter == (self._counter_half - 1)):
            m.d.sync += self.o_half_elapsed.eq(1)
        with m.Elif(self._counter == self._counter_max - 1):
            m.d.sync += self.o_elapsed.eq(1)

        return m

    def ports(self):
        return [self.i_start, self.o_elapsed, self.o_half_elapsed]
