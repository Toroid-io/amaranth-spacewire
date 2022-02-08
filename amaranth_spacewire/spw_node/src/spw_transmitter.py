import enum
from amaranth import *
from amaranth.sim import Simulator, Delay
from .ds_shift_registers import DSOutputCharSR
from .ds_encoder import DSEncoder
from .clock_divider import ClockDivider
from .clock_mux import ClockMux
from bitarray import bitarray
from amaranth_boards.de0_nano import DE0NanoPlatform


class WrongSignallingRate(Exception):
    def __init__(self, message):
        self.message = message


class WrongSourceFrequency(Exception):
    def __init__(self, message):
        self.message = message


class SpWTransmitterStates(enum.Enum):
    WAIT = 0
    SEND_NULL_A = 1
    SEND_NULL_B = 2
    SEND_NULL_C = 3
    WAIT_TX_START_CONTROL = 4
    WAIT_TX_START_DATA = 5
    SEND_TIME_A = 6
    SEND_TIME_B = 7
    SEND_TIME_C = 8


class SpWTransmitter(Elaboratable):
    TX_FREQ_RESET = 10e6
    MIN_TX_FREQ_USER = 2e6

    def __init__(self, srcfreq, txfreq, debug=False):
        self.i_reset = Signal()
        self.i_switch_to_user_tx_freq = Signal()
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

        self._debug = debug
        if debug:
            self.o_debug_encoder_reset_feedback = Signal()
            self.o_debug_mux_clk = Signal()
            self.o_debug_mux_sel = Signal()
            self.o_debug_fsm_state = Signal()
            self.o_debug_sr_input = Signal(8)

        if txfreq < SpWTransmitter.MIN_TX_FREQ_USER:
            self._MustUse__silence = True
            raise WrongSignallingRate("Signalling rate must be at least 2 Mb/s (provided {0} Mb/s)".format(txfreq/1e6))
        elif srcfreq < 2 * SpWTransmitter.TX_FREQ_RESET:
            self._MustUse__silence = True
            raise WrongSourceFrequency("The source frequency must be at least 2 times the reset transmit frequency. Expected > {0}, given {1}".format(2 * SpWTransmitter.TX_FREQ_RESET, srcfreq))
        elif srcfreq < 2 * txfreq:
            self._MustUse__silence = True
            raise WrongSourceFrequency("The source frequency must be at least 2 times the transmit frequency. Expected > {0}, given {1}".format(2 * txfreq, srcfreq))

    def elaborate(self, platform):
        m = Module()

        m.submodules.tr_clk_reset = tr_clk_reset = ClockDivider(self._srcfreq, SpWTransmitter.TX_FREQ_RESET)
        m.submodules.tr_clk_user = tr_clk_user = ClockDivider(self._srcfreq, self._txfreq)
        m.submodules.tr_clk_mux = tr_clk_mux = ClockMux()
        m.domains.tx = ClockDomain("tx", local=True)
        m.submodules.encoder = encoder = DomainRenamer("tx")(DSEncoder())
        m.submodules.sr = sr = DomainRenamer("tx")(DSOutputCharSR())

        # TODO: Const
        char_fct = Signal(8, reset=0b00000000)
        char_esc = Signal(8, reset=0b00000011)
        char_eop = Signal(8, reset=0b00000010)
        char_eep = Signal(8, reset=0b00000001)
        parity_control = Signal()
        parity_data = Signal()
        # One tx clock delay to hold d/s signals at reset
        encoder_reset = Signal(reset=1)
        encoder_reset_feedback = Signal()
        send_null = Signal()
        timecode_to_send = Signal(8)

        m.d.comb += [
            encoder.i_d.eq(sr.o_output),
            encoder.i_reset.eq(encoder_reset),
            encoder.i_en.eq(sr.o_active),
            sr.i_reset.eq(encoder_reset),
            self.o_d.eq(encoder.o_d),
            self.o_s.eq(encoder.o_s)
        ]

        m.d.tx += encoder_reset_feedback.eq(encoder_reset)
        with m.If(self.i_reset):
            m.d.sync += encoder_reset.eq(1)
        with m.Elif(encoder_reset_feedback):
            m.d.sync += encoder_reset.eq(0)

        with m.FSM() as tr_fsm:
            with m.State(SpWTransmitterStates.WAIT):
                with m.If(~self.i_reset & self.o_ready):
                    with m.If(self.i_send_char == 1):
                        m.d.sync += [
                            sr.i_send_data.eq(1),
                            sr.i_input.eq(self.i_char)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_DATA
                    with m.Elif(self.i_send_esc == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_esc)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_CONTROL
                    with m.Elif(self.i_send_fct == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_fct)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_CONTROL
                    with m.Elif(self.i_send_eop == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_eop)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_CONTROL
                    with m.Elif(self.i_send_eep == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_eep)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_CONTROL
                    with m.Elif(self.i_send_time == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_esc),
                            timecode_to_send.eq(self.i_char)
                        ]
                        m.next = SpWTransmitterStates.SEND_TIME_A
                    with m.Elif(send_null == 1):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(char_esc)
                        ]
                        m.next = SpWTransmitterStates.SEND_NULL_A
            with m.State(SpWTransmitterStates.SEND_NULL_A):
                with m.If(self.i_reset):
                    m.next = SpWTransmitterStates.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready == 0):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = SpWTransmitterStates.SEND_NULL_B
            with m.State(SpWTransmitterStates.SEND_NULL_B):
                with m.If(self.i_reset):
                    m.next = SpWTransmitterStates.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready == 1):
                    m.d.sync += [
                        sr.i_send_control.eq(1),
                        sr.i_input.eq(char_fct)
                    ]
                    m.next = SpWTransmitterStates.SEND_NULL_C
            with m.State(SpWTransmitterStates.SEND_NULL_C):
                with m.If(self.i_reset):
                    m.next = SpWTransmitterStates.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready == 0):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = SpWTransmitterStates.WAIT
            with m.State(SpWTransmitterStates.WAIT_TX_START_CONTROL):
                with m.If(self.i_reset):
                    m.next = SpWTransmitterStates.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready == 0):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = SpWTransmitterStates.WAIT
            with m.State(SpWTransmitterStates.WAIT_TX_START_DATA):
                with m.If(self.i_reset):
                    m.next = SpWTransmitterStates.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready == 0):
                    m.d.sync += sr.i_send_data.eq(0)
                    m.next = SpWTransmitterStates.WAIT
            with m.State(SpWTransmitterStates.SEND_TIME_A):
                with m.If(self.i_reset):
                    m.next = SpWTransmitterStates.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready == 0):
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                    ]
                    m.next = SpWTransmitterStates.SEND_TIME_B
            with m.State(SpWTransmitterStates.SEND_TIME_B):
                with m.If(self.i_reset):
                    m.next = SpWTransmitterStates.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready == 1):
                    m.d.sync += [
                        sr.i_send_data.eq(1),
                        sr.i_input.eq(timecode_to_send)
                    ]
                    m.next = SpWTransmitterStates.SEND_TIME_C
            with m.State(SpWTransmitterStates.SEND_TIME_C):
                with m.If(self.i_reset):
                    m.next = SpWTransmitterStates.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready == 0):
                    m.d.sync += [
                        sr.i_send_data.eq(0)
                    ]
                    m.next = SpWTransmitterStates.WAIT

            m.d.comb += self.o_ready.eq(tr_fsm.ongoing(SpWTransmitterStates.WAIT) & sr.o_ready & encoder.o_ready & ~encoder_reset)
            m.d.sync += send_null.eq(~self.i_send_char & ~self.i_send_eep & ~self.i_send_eop & ~self.i_send_esc & ~self.i_send_fct)

        m.d.comb += [
            tr_clk_mux.i_sel.eq(self.i_switch_to_user_tx_freq),
            tr_clk_mux.i_clk_a.eq(tr_clk_reset.o),
            tr_clk_mux.i_clk_b.eq(tr_clk_user.o),
            ClockSignal("tx").eq(tr_clk_mux.o_clk)
        ]

        if self._debug:
            m.d.comb += [
                self.o_debug_encoder_reset_feedback.eq(encoder_reset_feedback),
                self.o_debug_mux_clk.eq(tr_clk_mux.o_clk),
                self.o_debug_mux_sel.eq(tr_clk_mux.i_sel),
                self.o_debug_fsm_state.eq(tr_fsm.state),
                self.o_debug_sr_input.eq(sr.i_input)
            ]

        return m

    def ports(self):
        return [
            self.i_reset, self.i_char, self.i_send_char, self.i_send_fct,
            self.i_send_esc, self.i_send_eop, self.i_send_eep, self.i_send_time,
            self.o_ready, self.o_d, self.o_s,
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
