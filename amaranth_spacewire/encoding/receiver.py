from amaranth import *
from amaranth.lib.cdc import FFSynchronizer

from amaranth_spacewire.encoding.ds_shift_registers import DSInputControlCharSR, DSInputDataCharSR
from amaranth_spacewire.encoding.ds_decoder import DSDecoder
from amaranth_spacewire.encoding.ds_store_enable import DSStoreEnable
from amaranth_spacewire.encoding.spw_disconnect_detector import SpWDisconnectDetector
from amaranth_spacewire.misc.constants import *


class Receiver(Elaboratable):
    """A SpaceWire receiver.

    Parameters
    ----------
    srcfreq : int
        The main core frequency in Hz.
    disconnect_delay : int
        The link disconnect delay in seconds.

    Attributes
    ----------
    i_d : Signal(1), in
        Data signal from the Data/Strobe pair.
    i_s : Signal(1), in
        Strobe signal from the Data/Strobe pair.
    i_reset : Signal(1), in
        Reset signal.
    o_got_fct : Signal(1), out
        Indication that a Flow Control Token character was received.
    o_got_eep : Signal(1), out
        Indication that an Error End of Packet character was received.
    o_got_eop : Signal(1), out
        Indication that an End Of Packet character was received.
    o_got_esc : Signal(1), out
        Indication that an Escape character was received.
    o_got_null : Signal(1), out
        Indication that a Null character was received.
    o_got_timecode : Signal(1), out
        Indication that a Timecode was received.
    o_got_data : Signal(1), out
        Indication that a Data character was received.
    o_char : Signal(9), out
        The received data character. Only valid if ``o_got_data`` is asserted.
    o_parity_error : Signal(1), out
        Indication that a Parity Error was detected.
    o_read_error : Signal(1), out
        Indication that a Read Error was detected.
    o_escape_error : Signal(1), out
        Indication that an Escape Error was detected.
    o_disconnect_error : Signal(1), out
        Indication that a Disconnect Error was detected.
    """
    def __init__(self, srcfreq, disconnect_delay=850e-9):
        self.data = Signal()
        self.strobe = Signal()
        self.enable = Signal()
        self.got_fct = Signal()
        self.got_esc = Signal()
        self.got_null = Signal()
        self.got_bc = Signal()
        self.char = Signal(9)
        self.got_n_char = Signal()
        self.parity_error = Signal()
        self.read_error = Signal()
        self.esc_error = Signal()
        self.disconnect_error = Signal()

        self._srcfreq = srcfreq
        self._disconnect_delay = disconnect_delay

    def elaborate(self, platform):
        m = Module()
        m.submodules.ds_decoder = decoder = DSDecoder()
        m.submodules.store_en = store_en = DSStoreEnable()
        m.submodules.control_sr = control_sr = DSInputControlCharSR()
        m.submodules.data_sr = data_sr = DSInputDataCharSR()
        m.submodules.disc = disc = SpWDisconnectDetector(self._srcfreq, self._disconnect_delay)

        # Counter used to read 4 by 4 the shift register output.
        counter = Signal(4)
        # Counter limit based on the character type. 4 for control characters
        # and 10 for data characters.
        counter_limit = Signal(4)
        # Synchronisation flag that is 1 when we received the number of bits in
        # the current character.
        counter_full = Signal()
        # Last known parity running without errors.
        parity_prev = Signal()
        # Parity of the current control character (to be checked with the *next*
        # received character).
        parity_control_next = Signal()
        # Parity of the current data character (to be checked with the *next*
        # received character).
        parity_data_next = Signal()
        # This is the previous detected control char, waiting for the next one
        # to validate parity. It will only be output after validation.
        prev_control_char_wait_parity = Signal(4)
        # This is the previous detected data char, waiting for the next one to
        # validate parity. It will only be output after validation.
        prev_data_char_wait_parity = Signal(8)
        # Selection of the previous character detected. Used to drive the
        # correct output flags/registers.
        prev_char_type = Signal()
        # NULL detection
        prev_got_esc = Signal()
        # Silent double end of packet frop
        prev_got_eop = Signal()
        prev_got_eep = Signal()

        # Reset all signals
        with m.If(~self.enable):
            m.d.comb += [
                counter_full.eq(0),
                parity_control_next.eq(0),
                parity_data_next.eq(0)
            ]
            m.d.sync += [
                counter.eq(0),
                counter_limit.eq(0),
                parity_prev.eq(0),
                prev_control_char_wait_parity.eq(0),
                prev_data_char_wait_parity.eq(0),
                prev_char_type.eq(0),
                prev_got_esc.eq(0),
                prev_got_eop.eq(0),
                prev_got_eep.eq(0),
                self.char.eq(0),
                self.parity_error.eq(0),
                self.read_error.eq(0),
                self.esc_error.eq(0)
            ]

        m.submodules += FFSynchronizer(self.data, decoder.i_d, reset=0)
        m.submodules += FFSynchronizer(self.strobe, decoder.i_s, reset=0)

        m.d.comb += [
            store_en.i_reset.eq(~self.enable),
            store_en.i_d.eq(decoder.o_d),
            store_en.i_clk_ddr.eq(decoder.o_clk_ddr),
            control_sr.i_reset.eq(~self.enable),
            control_sr.i_input.eq(store_en.o_d),
            control_sr.i_store.eq(store_en.o_store_en),
            data_sr.i_reset.eq(~self.enable),
            data_sr.i_input.eq(store_en.o_d),
            data_sr.i_store.eq(store_en.o_store_en),
            parity_control_next.eq(control_sr.o_parity_next),
            parity_data_next.eq(data_sr.o_parity_next),
            disc.i_store_en.eq(store_en.o_store_en),
            disc.i_reset.eq(~self.enable),
            self.disconnect_error.eq(disc.o_disconnected)
        ]

        m.d.comb += [
            counter_full.eq(counter == counter_limit)
        ]

        # By default, set these to zero. They will be overriden when a character
        # is validated in the FSM.
        m.d.sync += [
            self.got_n_char.eq(0),
            self.got_fct.eq(0),
            self.got_esc.eq(0),
            self.got_null.eq(0),
            self.got_bc.eq(0)
        ]

        # Manage counter
        with m.If(~self.enable):
            m.d.sync += counter.eq(0)
        with m.Elif(store_en.o_store_en & counter_full):
            m.d.sync += counter.eq(1)
        with m.Elif(counter_full):
            # Put the counter to zero to avoid double output (remember
            # the sync clock is faster than the character clock)
            m.d.sync += counter.eq(0)
        with m.Elif(store_en.o_store_en):
            m.d.sync += counter.eq(counter + 1)
        with m.Else():
            m.d.sync += counter.eq(counter)

        # Start expecting a control char ESC
        with m.FSM() as fsm:
            with m.State("SYNC"):
                with m.If(self.enable & control_sr.o_detected_esc):
                    m.d.sync += [
                        counter.eq(0),
                        parity_prev.eq(parity_control_next),
                        prev_control_char_wait_parity.eq(control_sr.o_char),
                        prev_char_type.eq(1)
                    ]
                    m.next = "READ_HEADER"
            with m.State("READ_HEADER"):
                with m.If(~self.enable):
                    m.next = "SYNC"
                with m.Elif(counter == 2):
                    with m.If(control_sr.o_char[3] == 1):
                        m.next = "READ_CONTROL_CHAR"
                        m.d.sync += counter_limit.eq(4)
                    with m.Else():
                        m.next = "READ_DATA_CHAR"
                        m.d.sync += counter_limit.eq(10)

                    # This XOR operation needs to be 1 to have a valid parity
                    with m.If((parity_prev ^ control_sr.o_char[2]) ^ control_sr.o_char[3]):
                        with m.If(prev_char_type):
                            with m.Switch(prev_control_char_wait_parity):
                                with m.Case("001-"):
                                    with m.If(prev_got_esc):
                                        m.d.sync += [self.got_null.eq(1), prev_got_esc.eq(0)]
                                    with m.Else():
                                        m.d.sync += [self.got_fct.eq(1), prev_got_eop.eq(0), prev_got_eep.eq(0)]
                                with m.Case("101-"):
                                    with m.If(prev_got_esc):
                                        m.d.sync += [self.esc_error.eq(1)]
                                        m.next = "ERROR"
                                    with m.Else():
                                        m.d.sync += [self.got_n_char.eq(1), prev_got_eop.eq(1), prev_got_eep.eq(0)]
                                        m.d.sync += self.char.eq(CHAR_EOP)
                                with m.Case("011-"):
                                    with m.If(prev_got_esc):
                                        m.d.sync += [self.esc_error.eq(1)]
                                        m.next = "ERROR"
                                    with m.Else():
                                        m.d.sync += [self.got_n_char.eq(1), prev_got_eep.eq(1), prev_got_eop.eq(0)]
                                        m.d.sync += self.char.eq(CHAR_EEP)
                                with m.Case("111-"):
                                    with m.If(prev_got_esc):
                                        m.d.sync += [self.esc_error.eq(1)]
                                        m.next = "ERROR"
                                    with m.Else():
                                        m.d.sync += [self.got_esc.eq(1), prev_got_esc.eq(1), prev_got_eep.eq(0), prev_got_eop.eq(0)]
                        with m.Else():
                            with m.If(prev_got_esc):
                                m.d.sync += [self.got_bc.eq(1), prev_got_esc.eq(0)]
                            with m.Else():
                                m.d.sync += self.got_n_char.eq(1)
                            m.d.sync += self.char.eq(Cat(prev_data_char_wait_parity, prev_char_type))
                            m.d.sync += [prev_got_eop.eq(0), prev_got_eep.eq(0)]
                    with m.Else():
                        m.d.sync += [
                            self.parity_error.eq(1)
                        ]
                        m.next = "ERROR"
            with m.State("READ_CONTROL_CHAR"):
                with m.If(~self.enable):
                    m.next = "SYNC"
                with m.Elif(counter_full & control_sr.o_detected):
                    m.d.sync += [
                        parity_prev.eq(parity_control_next),
                        prev_control_char_wait_parity.eq(control_sr.o_char),
                        prev_char_type.eq(1)
                    ]
                    m.next = "READ_HEADER"
                with m.Elif(counter_full & ~control_sr.o_detected):
                    m.d.sync += self.read_error.eq(1)
                    m.next = "ERROR"
            with m.State("READ_DATA_CHAR"):
                with m.If(~self.enable):
                    m.next = "SYNC"
                with m.Elif(counter_full & data_sr.o_detected):
                    m.d.sync += [
                        parity_prev.eq(parity_data_next),
                        prev_data_char_wait_parity.eq(data_sr.o_char[2:10]),
                        prev_char_type.eq(0)
                    ]
                    m.next = "READ_HEADER"
                with m.Elif(counter_full & ~control_sr.o_detected):
                    m.d.sync += self.read_error.eq(1)
                    m.next = "ERROR"
            with m.State("ERROR"):
                with m.If(~self.enable):
                    m.next = "SYNC"

        return m

    def ports(self):
        return [
            self.data, self.strobe, self.enable, self.got_fct,
            self.got_esc, self.got_null, self.char,
            self.got_n_char, self.parity_error, self.read_error,
            self.esc_error, self.disconnect_error, self.got_bc
        ]
