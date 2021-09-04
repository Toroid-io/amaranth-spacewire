from nmigen import *
from nmigen.sim import Simulator, Delay
from ds_char_shift_register import DSCharControlShiftRegister, DSCharDataShiftRegister
from ds import DSDecoder
from store_enable import DSStoreEnable
from bitarray import bitarray


class DSReceiver(Elaboratable):
    def __init__(self):
        self.i_d = Signal()
        self.i_s = Signal()
        self.i_reset = Signal()
        self.o_got_fct = Signal()
        self.o_got_eep = Signal()
        self.o_got_eop = Signal()
        self.o_got_esc = Signal()
        self.o_got_null = Signal()
        self.o_data_char = Signal(8)
        self.o_got_data = Signal()
        self.o_parity_error = Signal()
        self.o_read_error = Signal()
        self.o_escape_error = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules.decoder = decoder = DSDecoder()
        m.submodules.store_en = store_en = DSStoreEnable()
        m.submodules.control_sr = control_sr = DSCharControlShiftRegister()
        m.submodules.data_sr = data_sr = DSCharDataShiftRegister()

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
        # Parity of the current control or data character (holding information
        # about the *prev*ious received character). This value is the same for
        # control/data because they are the first two bits of each shift
        # register.
        parity_char_prev = Signal()
        # Parity computed using the previous stored parity and the received bits
        # of the shift registers. It should always be '1'.
        parity_check = Signal()
        # Parity of the current control character (to be checked with the *next*
        # received character).
        parity_control_next = Signal()
        # Parity of the current control character (to be checked with the *next*
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

        # Reset all signals
        with m.If(self.i_reset):
            m.d.comb += [
                counter_full.eq(0),
                parity_char_prev.eq(0),
                parity_check.eq(0),
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
                self.o_data_char.eq(0),
                self.o_parity_error.eq(0),
                self.o_read_error.eq(0),
                self.o_escape_error.eq(0)
            ]

        m.d.comb += [
            store_en.i_reset.eq(self.i_reset),
            decoder.i_d.eq(self.i_d),
            decoder.i_s.eq(self.i_s),
            store_en.i_d.eq(decoder.o_d),
            store_en.i_clk_ddr.eq(decoder.o_clk_ddr),
            control_sr.i_input.eq(store_en.o_d),
            control_sr.i_store.eq(store_en.o_store_en),
            data_sr.i_input.eq(store_en.o_d),
            data_sr.i_store.eq(store_en.o_store_en),
            parity_control_next.eq(control_sr.o_parity_next),
            parity_data_next.eq(data_sr.o_parity_next),
            parity_check.eq(parity_prev ^ parity_char_prev)
        ]

        m.d.comb += [
            counter_full.eq(counter == counter_limit)
        ]

        # By default, set these to zero. They will be overriden when a character
        # is validated in the FSM.
        m.d.sync += self.o_got_data.eq(0)
        m.d.sync += self.o_got_eep.eq(0)
        m.d.sync += self.o_got_eop.eq(0)
        m.d.sync += self.o_got_fct.eq(0)
        m.d.sync += self.o_got_esc.eq(0)
        m.d.sync += self.o_got_null.eq(0)

        # Manage counter
        with m.If(self.i_reset == 1):
            m.d.sync += counter.eq(0)
        with m.Elif((store_en.o_store_en & counter_full) == 1):
            m.d.sync += counter.eq(1)
        with m.Elif(counter_full == 1):
            # Put the counter to zero to avoid double output (remember
            # the sync clock is faster than the character clock)
            m.d.sync += counter.eq(0)
        with m.Elif(store_en.o_store_en == 1):
            m.d.sync += counter.eq(counter + 1)
        with m.Else():
            m.d.sync += counter.eq(counter)

        # Start expecting a control char ESC
        with m.FSM() as fsm:
            with m.State("SYNC"):
                with m.If(~self.i_reset & control_sr.o_detected_esc):
                    m.d.sync += [
                        counter.eq(0),
                        parity_prev.eq(parity_control_next),
                        prev_control_char_wait_parity.eq(control_sr.o_char),
                        prev_char_type.eq(0)
                    ]
                    m.next = "READ_HEADER"
            with m.State("READ_HEADER"):
                with m.If(self.i_reset == 1):
                    m.next = "SYNC"
                with m.Elif(counter == 2):
                    with m.If(control_sr.o_char[3] == 1):
                        m.next = "READ_CONTROL_CHAR"
                        m.d.sync += counter_limit.eq(4)
                    with m.Else():
                        m.next = "READ_DATA_CHAR"
                        m.d.sync += counter_limit.eq(10)

                    with m.If(((parity_prev ^ control_sr.o_char[2]) ^ control_sr.o_char[3]) == 1):
                        with m.If(prev_char_type == 0):
                            with m.Switch(prev_control_char_wait_parity):
                                with m.Case("001-"):
                                    with m.If(prev_got_esc == 1):
                                        m.d.sync += [self.o_got_null.eq(1), prev_got_esc.eq(0)]
                                    with m.Else():
                                        m.d.sync += [self.o_got_fct.eq(1), prev_got_esc.eq(0)]
                                with m.Case("101-"):
                                    with m.If(prev_got_esc == 1):
                                        m.d.sync += [self.o_escape_error.eq(1)]
                                        m.next = "ERROR"
                                    with m.Else():
                                        m.d.sync += [self.o_got_eop.eq(1), prev_got_esc.eq(0)]
                                with m.Case("010-"):
                                    with m.If(prev_got_esc == 1):
                                        m.d.sync += [self.o_escape_error.eq(1)]
                                        m.next = "ERROR"
                                    with m.Else():
                                        m.d.sync += [self.o_got_eep.eq(1), prev_got_esc.eq(0)]
                                with m.Case("111-"):
                                    with m.If(prev_got_esc == 1):
                                        m.d.sync += [self.o_escape_error.eq(1)]
                                        m.next = "ERROR"
                                    with m.Else():
                                        m.d.sync += [self.o_got_esc.eq(1), prev_got_esc.eq(1)]
                        with m.Else():
                            m.d.sync += [
                                self.o_got_data.eq(1),
                                self.o_data_char.eq(prev_data_char_wait_parity)
                            ]
                    with m.Else():
                        m.d.sync += [
                            self.o_parity_error.eq(1)
                        ]
                        m.next = "ERROR"
            with m.State("READ_CONTROL_CHAR"):
                with m.If(self.i_reset == 1):
                    m.next = "SYNC"
                with m.Elif((counter_full & control_sr.o_detected) == 1):
                    m.d.sync += [
                        parity_prev.eq(parity_control_next),
                        prev_control_char_wait_parity.eq(control_sr.o_char),
                        prev_char_type.eq(0)
                    ]
                    m.next = "READ_HEADER"
                with m.Elif((counter_full & ~control_sr.o_detected) == 1):
                    m.d.sync += self.o_read_error.eq(1)
                    m.next = "ERROR"
            with m.State("READ_DATA_CHAR"):
                with m.If(self.i_reset == 1):
                    m.next = "SYNC"
                with m.Elif((counter_full & data_sr.o_detected) == 1):
                    m.d.sync += [
                        parity_prev.eq(parity_data_next),
                        prev_data_char_wait_parity.eq(data_sr.o_char[2:10]),
                        prev_char_type.eq(1)
                    ]
                    m.next = "READ_HEADER"
                with m.Elif((counter_full & ~control_sr.o_detected) == 1):
                    m.d.sync += self.o_read_error.eq(1)
                    m.next = "ERROR"
            with m.State("ERROR"):
                with m.If(self.i_reset):
                    m.next = "SYNC"

        return m

    def ports(self):
        return [self.i_d, self.i_s]


if __name__ == '__main__':
    def test_receiver():
        i_d = Signal()
        i_s = Signal()
        i_reset = Signal(reset=1)

        m = Module()
        m.submodules.rv = rv = DSReceiver()
        m.d.comb += [
            rv.i_d.eq(i_d),
            rv.i_s.eq(i_s),
            rv.i_reset.eq(i_reset)
        ]

        sim = Simulator(m)
        sim.add_clock(1e-6)

        global prev_d
        global prev_s
        global prev_parity
        prev_d = False
        prev_s = False
        prev_parity = False

        def ds_send_d(d):
            global prev_d
            global prev_s
            yield i_d.eq(d)
            if d != prev_d:
                yield i_s.eq(prev_s)
            else:
                prev_s = not prev_s
                yield i_s.eq(prev_s)
            prev_d = d
            yield Delay(2.2e-6)

        def ds_send_char(b):
            global prev_parity
            data = bitarray(endian='little')
            data.frombytes(b.encode())
            parity = not (prev_parity ^ False)
            next_parity = False
            for i in range(8):
                next_parity = next_parity ^ data[i]
            prev_parity = next_parity
            yield from ds_send_d(parity)
            yield from ds_send_d(0)
            for i in range(8):
                yield from ds_send_d(data[i])

        def ds_send_null():
            global prev_parity
            parity = not (prev_parity ^ True)
            prev_parity = False
            yield from ds_send_d(parity)
            yield from ds_send_d(1)
            yield from ds_send_d(1)
            yield from ds_send_d(1)
            parity = not (prev_parity ^ True)
            prev_parity = False
            yield from ds_send_d(parity)
            yield from ds_send_d(1)
            yield from ds_send_d(0)
            yield from ds_send_d(0)

        def ds_send_wrong_null():
            global prev_parity
            parity = not (prev_parity ^ True)
            prev_parity = False
            yield from ds_send_d(parity)
            yield from ds_send_d(1)
            yield from ds_send_d(1)
            yield from ds_send_d(1)
            parity = not (prev_parity ^ True)
            prev_parity = False
            yield from ds_send_d(not parity)
            yield from ds_send_d(1)
            yield from ds_send_d(0)
            yield from ds_send_d(0)

        def decoder_test():
            yield Delay(50e-6)
            for _ in range(30):
                yield from ds_send_null()
            yield from ds_send_wrong_null()
            yield from ds_send_null()
            yield from ds_send_null()
            yield from ds_send_char('A')
            yield from ds_send_char('N')
            yield from ds_send_char('D')
            yield from ds_send_char('R')
            yield from ds_send_char('E')
            yield from ds_send_char('S')
            for _ in range(30):
                yield from ds_send_null()

        def reset_manage():
            for _ in range(25):
                yield
            yield i_reset.eq(0)
            while True:
                if (yield rv.o_parity_error == 1):
                    yield i_reset.eq(1)
                    yield
                    yield i_reset.eq(0)
                yield

        sim.add_process(decoder_test)
        sim.add_sync_process(reset_manage)
        with sim.write_vcd("ds_receiver.vcd", "ds_receiver.gtkw", traces=rv.ports()):
            sim.run_until(2e-3)


    test_receiver()
