import enum
from amaranth import *
from amaranth.sim import Simulator, Delay
from .ds_shift_registers import DSOutputCharSR
from .ds_encoder import DSEncoder
from ..misc.clock_divider import ClockDivider
from ..misc.clock_mux import ClockMux
from bitarray import bitarray


class WrongSignallingRate(Exception):
    def __init__(self, message):
        self.message = message


class WrongSourceFrequency(Exception):
    def __init__(self, message):
        self.message = message


class SpWTransmitterStates(enum.Enum):
    WAIT                    = 0
    WAIT_TX_START_DATA      = 1
    WAIT_TX_START_CONTROL   = 2
    SEND_TIME_A             = 3
    SEND_NULL_A             = 4
    SEND_NULL_B             = 5
    SEND_NULL_C             = 6
    SEND_TIME_B             = 7
    SEND_TIME_C             = 8


class SpWTransmitter(Elaboratable):
    TX_FREQ_RESET = 10e6
    MIN_TX_FREQ_USER = 2e6
    CHAR_FCT = Const(0b00000000)
    CHAR_ESC = Const(0b00000011)
    CHAR_EOP = Const(0b00000010)
    CHAR_EEP = Const(0b00000001)

    def __init__(self, srcfreq, rstfreq=TX_FREQ_RESET, txfreq=TX_FREQ_RESET, debug=False):
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

        self._srcfreq = srcfreq
        self._rstfreq = rstfreq
        self._txfreq = txfreq

        self._debug = debug
        if debug:
            self.o_debug_encoder_reset_feedback = Signal()
            self.o_debug_mux_clk = Signal()
            self.o_debug_mux_sel = Signal()
            self.o_debug_fsm_state = Signal(SpWTransmitterStates)
            self.o_debug_sr_input = Signal(8)

        if txfreq < SpWTransmitter.MIN_TX_FREQ_USER:
            raise WrongSignallingRate("Signalling rate must be at least 2 Mb/s (provided {0} Mb/s)".format(txfreq/1e6))
        elif srcfreq < 2 * rstfreq:
            raise WrongSourceFrequency("The source frequency must be at least 2 times the reset transmit frequency. Expected > {0}, given {1}".format(2 * SpWTransmitter.rstfreq, srcfreq))
        elif srcfreq < 2 * txfreq:
            raise WrongSourceFrequency("The source frequency must be at least 2 times the transmit frequency. Expected > {0}, given {1}".format(2 * txfreq, srcfreq))

    def elaborate(self, platform):
        m = Module()

        m.submodules.tr_clk_reset = tr_clk_reset = ClockDivider(self._srcfreq, self._rstfreq)
        m.submodules.tr_clk_user = tr_clk_user = ClockDivider(self._srcfreq, self._txfreq)
        m.submodules.tr_clk_mux = tr_clk_mux = ClockMux()
        m.domains.tx = ClockDomain("tx", local=True)
        m.submodules.encoder = encoder = DomainRenamer("tx")(DSEncoder())
        m.submodules.sr = sr = DomainRenamer("tx")(DSOutputCharSR())

        parity_control = Signal()
        parity_data = Signal()
        # One tx clock delay to hold d/s signals at reset
        encoder_reset = Signal(reset=1)
        encoder_reset_feedback_1 = Signal()
        encoder_reset_feedback_2 = Signal()
        timecode_to_send = Signal(8)

        m.d.comb += [
            encoder.i_d.eq(sr.o_output),
            encoder.i_reset.eq(encoder_reset),
            encoder.i_en.eq(sr.o_active),
            sr.i_reset.eq(encoder_reset),
            self.o_d.eq(encoder.o_d),
            self.o_s.eq(encoder.o_s)
        ]

        m.d.tx += [encoder_reset_feedback_1.eq(encoder_reset), encoder_reset_feedback_2.eq(encoder_reset_feedback_1)]
        with m.If(self.i_reset):
            m.d.sync += encoder_reset.eq(1)
        with m.Elif(encoder_reset_feedback_2):
            m.d.sync += encoder_reset.eq(0)

        with m.FSM() as tr_fsm:
            with m.State(SpWTransmitterStates.WAIT):
                with m.If(~self.i_reset & self.o_ready):
                    with m.If(self.i_send_char):
                        m.d.sync += [
                            sr.i_send_data.eq(1),
                            sr.i_input.eq(self.i_char)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_DATA
                    with m.Elif(self.i_send_esc):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(SpWTransmitter.CHAR_ESC)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_CONTROL
                    with m.Elif(self.i_send_fct):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(SpWTransmitter.CHAR_FCT)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_CONTROL
                    with m.Elif(self.i_send_eop):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(SpWTransmitter.CHAR_EOP)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_CONTROL
                    with m.Elif(self.i_send_eep):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(SpWTransmitter.CHAR_EEP)
                        ]
                        m.next = SpWTransmitterStates.WAIT_TX_START_CONTROL
                    with m.Elif(self.i_send_time):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(SpWTransmitter.CHAR_ESC),
                            timecode_to_send.eq(self.i_char)
                        ]
                        m.next = SpWTransmitterStates.SEND_TIME_A
                    with m.Else():
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(SpWTransmitter.CHAR_ESC)
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
                        sr.i_input.eq(SpWTransmitter.CHAR_FCT)
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
