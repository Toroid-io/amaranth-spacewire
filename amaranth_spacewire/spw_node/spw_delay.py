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
    i_reset : Signal(1), in
        Reset signal.
    i_start : Signal(1), in
        Indication that the countdown should start. Once started, it is ignored
        until the delay has elapsed, or ``i_reset`` is asserted.
    o_half_elapsed : Signal(1), out
        Half-time elapsed indication.
    o_elapsed : Signal(1), out
        Full-time elapsed indication.
    """
    def __init__(self, srcfreq, delay, strategy='at_least'):
        self.i_reset = Signal()
        self.i_start = Signal()
        self.o_half_elapsed = Signal()
        self.o_elapsed = Signal()
        self._ticks = _ticksForDelay(srcfreq, delay, strategy=strategy)
        self._strategy = strategy

    def elaborate(self, platform):
        m = Module()

        counter = Signal(bits_for(self._ticks))
        if self._strategy == 'at_least':
            counter_half = math.ceil(self._ticks/2)
        else:
            counter_half = math.floor(self._ticks/2)

        with m.FSM() as fsm:
            with m.State("WAIT"):
                with m.If((self.i_start & ~self.i_reset) == 1):
                    m.next = "DELAY"
                with m.Elif(self.i_reset == 1):
                    m.d.sync += [self.o_elapsed.eq(0), self.o_half_elapsed.eq(0)]
            with m.State("DELAY"):
                with m.If(self.i_reset == 1):
                    m.d.sync += counter.eq(0)
                    m.next = "WAIT"
                with m.Else():
                    with m.If(counter == (counter_half - 1)):
                        m.d.sync += self.o_half_elapsed.eq(1)

                    with m.If(counter == self._ticks - 1):
                        m.d.sync += [
                            counter.eq(0),
                            self.o_elapsed.eq(1)
                        ]
                        m.next = "WAIT"
                    with m.Else():
                        m.d.sync += counter.eq(counter + 1)

        return m

    def ports(self):
        return [self.i_start, self.o_elapsed, self.o_half_elapsed]

if __name__ == '__main__':
    i_start = Signal()
    m = Module()
    m.submodules.delay = delay = SpWDelay(1.3e6, 34e-6)
    m.d.comb += delay.i_start.eq(i_start)

    sim = Simulator(m)
    sim.add_clock(1/1.3e6)

    def test():
        for _ in range(20):
            yield
        yield i_start.eq(1)
        yield
        yield
        yield i_start.eq(0)
        while ((yield delay.o_elapsed) == 0):
            yield
        for _ in range(20):
            yield

    sim.add_sync_process(test)
    with sim.write_vcd("vcd/spw_delay.vcd", "gtkw/spw_delay.gtkw", traces=delay.ports()):
        sim.run()