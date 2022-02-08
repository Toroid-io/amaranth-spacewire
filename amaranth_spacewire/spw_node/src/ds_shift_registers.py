from amaranth import *
from amaranth.utils import bits_for
from amaranth.sim import Simulator

#                             MSB-LSB
DS_CHAR_FCT_MATCHER         = '001-'
DS_CHAR_EOP_NORMAL_MATCHER  = '101-'
DS_CHAR_EOP_ERROR_MATCHER   = '011-'
DS_CHAR_ESC_MATCHER         = '111-'
DS_CHAR_DATA_MATCHER        = '--------0-'


class DSOutputCharSR(Elaboratable):
    """Shift register that outputs a data-char or a control-char based on its
    inputs.

    The ``o_ready`` and ``o_active`` outputs are complementary at all times but
    at reset, where both are deasserted.

    Attributes
    ----------
    i_reset : Signal(1), in
        Soft reset
    i_input : Signal(8), in
        Character to be sent next, can be a data-char or a control-char. If a
        control char is sent, only the two LSBs are read.
    i_send_data : Signal(1), in
        Indication that a data-char needs to be sent next.
    i_send_control : Signal(1), in
        Indication that a control-char needs to be sent next.
    o_output : Signal(1), out
        Serial output. This includes a parity bit, the data/control bit and the
        character bits.
    o_ready : Signal(1), out
        Indication that we can set ``i_input`` and ``i_send_data`` or
        ``i_send_control`` to the next valid information. Deasserted when the
        information started to be treated.
    o_active : Signal(1), out
        Indication that a transfer is in progress. Asserted when the
        information started to be treated.
    """
    def __init__(self):
        self.i_reset = Signal()
        self.i_input = Signal(8)
        self.i_send_data = Signal()
        self.i_send_control = Signal()
        self.o_output = Signal()
        self.o_ready = Signal()
        self.o_active = Signal()

    def elaborate(self, platform):
        m = Module()

        char_to_send = Signal(8)
        counter = Signal(4)
        counter_limit = Signal(4)
        parity_prev = Signal()
        parity_to_send = Signal()
        send_control = Signal()

        m.d.comb += parity_to_send.eq(~(parity_prev ^ self.i_send_control))

        with m.FSM() as fsm:
            with m.State("WAIT"):
                with m.If(self.i_reset):
                    m.d.sync += [self.o_ready.eq(0), self.o_active.eq(0)]
                with m.Elif(~self.i_reset & (self.i_send_control | self.i_send_data)):
                    m.d.sync += [
                        char_to_send.eq(self.i_input),
                        self.o_ready.eq(0),
                        counter.eq(1),
                        self.o_output.eq(parity_to_send),
                        parity_prev.eq(0),
                        send_control.eq(self.i_send_control),
                        self.o_active.eq(1)
                    ]
                    m.next = "SEND_TYPE"
                with m.Else():
                    m.d.sync += [self.o_ready.eq(1), self.o_active.eq(0)]

                with m.If(self.i_send_control & ~self.i_reset):
                    m.d.sync += counter_limit.eq(4)
                with m.Elif(self.i_send_data & ~self.i_reset):
                    m.d.sync += counter_limit.eq(10)
            with m.State("SEND_TYPE"):
                m.d.sync += [
                    self.o_output.eq(send_control),
                    counter.eq(counter + 1),
                ]

                with m.If(self.i_reset):
                    m.next = "WAIT"
                with m.Elif(counter == (counter_limit - 3)):
                    m.d.sync += self.o_ready.eq(1)
                    m.next = "SEND_CONTENT"
                with m.Else():
                    m.next = "SEND_CONTENT"
            with m.State("SEND_CONTENT"):
                with m.If(self.i_reset):
                    m.next = "WAIT"
                with m.Else():
                    for i in range(7):
                        m.d.sync += char_to_send[i].eq(char_to_send[i + 1])
                    m.d.sync += [
                        self.o_output.eq(char_to_send[0]),
                        char_to_send[7].eq(0),
                        parity_prev.eq(parity_prev ^ char_to_send[0])
                    ]

                with m.If(counter == (counter_limit - 3)):
                    m.d.sync += [
                        counter.eq(counter + 1),
                        self.o_ready.eq(1)
                    ]
                with m.Elif(counter == (counter_limit - 1)):
                    m.d.sync += [
                        counter.eq(0)
                    ]
                    m.next = "WAIT"
                with m.Else():
                    m.d.sync += [
                        counter.eq(counter + 1)
                    ]

        return m

    def ports(self):
        return [
            self.i_reset, self.i_input, self.i_send_data, self.i_send_control,
            self.o_output, self.o_ready, self.o_active
        ]


class DSInputCharSR(Elaboratable):
    _doc_template = """
    {description}


    Parameters
    ----------
    size : int
        The register size in bits.
    {parameters}

    Attributes
    ----------
    i_input : Signal(1), in
        Bit value to store whenever ``i_store`` is asserted.
    i_store : Signal(1), in
        Indication that the current value of ``i_input`` should be stored.
    {i_attributes}
    o_char : Signal(size), out
        Parallel output. This includes a parity bit, the data/control bit and the
        character bits.
    o_parity_next : Signal(1), out
        Computed parity of the current character in ``o_char``.
    {o_attributes}
    """

    __doc__ = _doc_template.format(description="""
    Shift register that stores the serialized input.
    """,
    parameters="", i_attributes="", o_attributes="")

    def __init__(self, size):
        self.i_input = Signal()
        self.i_store = Signal()
        self.o_char = Signal(size)
        self.o_parity_next = Signal()
        self._size = size

    def elaborate(self, platform):
        m = Module()
        size = self.o_char.shape().width

        parities = Signal(self._size)

        # Bits 0 and 1 are not used to compute parity (parity itself and
        # data/control bit)
        m.d.comb += parities[0].eq(self.o_char[2] ^ self.o_char[3])
        # - 4 accounts for parity bit, data/control bit and the already-used
        # bits on the previous line
        for i in range(self._size - 4):
            m.d.comb += parities[i + 1].eq(parities[i] ^ self.o_char[i + 4])
        m.d.comb += self.o_parity_next.eq(parities[-1])

        with m.If(self.i_store == 1):
            for bit in range(size - 1):
                m.d.sync += self.o_char[bit].eq(self.o_char[bit + 1])
            m.d.sync += self.o_char[size - 1].eq(self.i_input)

        return m

    def ports(self):
        return [self.i_input, self.i_store, self.o_char, self.o_parity_next]


class DSInputControlCharSR(DSInputCharSR):
    __doc__=DSInputCharSR._doc_template.format(
    description="""
    Shift register that stores the serialized input and decodes
    control-characters.
    """.strip(),
    parameters="",
    i_attributes="",
    o_attributes="""
    o_detected_fct : Signal(1), out
        Indication that an FCT control symbol has been detected in ``o_char``.
    o_detected_eop : Signal(1), out
        Indication that an EOP control symbol has been detected in ``o_char``.
    o_detected_eep : Signal(1), out
        Indication that an EEP control symbol has been detected in ``o_char``.
    o_detected_esc : Signal(1), out
        Indication that an ESC control symbol has been detected in ``o_char``.
    o_detected : Signal(1), out
        Indication that a control symbol has been detected in ``o_char``.
    """,
    )

    def __init__(self):
        super().__init__(4)
        self.o_detected_fct = Signal()
        self.o_detected_eop = Signal()
        self.o_detected_eep = Signal()
        self.o_detected_esc = Signal()
        self.o_detected = Signal()

    def elaborate(self, platform):
        m = super().elaborate(platform)

        m.d.comb += [
            self.o_detected.eq(self.o_detected_eep | self.o_detected_eop | self.o_detected_esc | self.o_detected_fct),
        ]

        with m.Switch(self.o_char):
            with m.Case(DS_CHAR_FCT_MATCHER):
                m.d.comb += self.o_detected_fct.eq(1)
            with m.Case(DS_CHAR_EOP_NORMAL_MATCHER):
                m.d.comb += self.o_detected_eop.eq(1)
            with m.Case(DS_CHAR_EOP_ERROR_MATCHER):
                m.d.comb += self.o_detected_eep.eq(1)
            with m.Case(DS_CHAR_ESC_MATCHER):
                m.d.comb += self.o_detected_esc.eq(1)

        return m

    def ports(self):
        return super().ports() + [
            self.o_detected_fct, self.o_detected_eop, self.o_detected_eep,
            self.o_detected_esc
        ]


class DSInputDataCharSR(DSInputCharSR):
    __doc__=DSInputCharSR._doc_template.format(
    description="""
    Shift register that stores the serialized input and decodes
    data-characters.
    """.strip(),
    parameters="",
    i_attributes="",
    o_attributes="""
    o_detected : Signal(1), out
        Indication that a data character has been detected in ``o_char``.
    """,
    )

    def __init__(self):
        super().__init__(10)
        self.o_detected = Signal()

    def elaborate(self, platform):
        m = super().elaborate(platform)

        with m.If(self.o_char.matches(DS_CHAR_DATA_MATCHER)):
            m.d.comb += self.o_detected.eq(1)

        return m

    def ports(self):
        return super().ports() + [
            self.o_detected,
        ]


if __name__ == '__main__':
    def test_base_sr():
        i_input = Signal()
        i_store = Signal()
        m = Module()
        m.submodules.sr = sr = DSInputCharSR(4)
        m.d.comb += [
            sr.i_input.eq(i_input),
            sr.i_store.eq(i_store)
        ]

        sim = Simulator(m)

        def test():
            yield i_input.eq(1)
            yield i_store.eq(0)
            yield
            yield
            yield
            yield i_store.eq(1)
            yield
            yield i_store.eq(0)
            yield
            yield
            yield i_store.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield i_input.eq(0)
            yield
            yield
            yield

        sim.add_clock(1e-6)
        sim.add_sync_process(test)

        with sim.write_vcd("vcd/ds_input_char_sr.vcd", "gtkw/ds_input_char_sr.gtkw", traces=sr.ports()):
            sim.run()

    def test_control_sr():
        i_input = Signal()
        i_store = Signal()
        m = Module()
        m.submodules.sr = sr = DSInputControlCharSR()
        m.d.comb += [
            sr.i_input.eq(i_input),
            sr.i_store.eq(i_store)
        ]

        sim = Simulator(m)

        def test():
            yield i_input.eq(1)
            yield i_store.eq(0)
            yield
            yield
            yield
            yield i_store.eq(1)
            yield
            yield i_store.eq(0)
            yield
            yield
            yield i_store.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield i_input.eq(0)
            yield
            yield
            yield

        sim.add_clock(1e-6)
        sim.add_sync_process(test)

        with sim.write_vcd("vcd/ds_input_control_char_sr.vcd", "gtkw/ds_input_control_char_sr.gtkw", traces=sr.ports()):
            sim.run()

    def test_data_sr():
        i_input = Signal()
        i_store = Signal()
        m = Module()
        m.submodules.sr = sr = DSInputDataCharSR()
        m.d.comb += [
            sr.i_input.eq(i_input),
            sr.i_store.eq(i_store)
        ]

        sim = Simulator(m)

        def test():
            yield i_input.eq(1)
            yield i_store.eq(0)
            yield
            yield
            yield
            yield i_store.eq(1)
            yield
            yield i_store.eq(0)
            yield
            yield
            yield i_input.eq(0)
            yield i_store.eq(1)
            yield
            yield
            yield
            yield i_input.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield

        sim.add_clock(1e-6)
        sim.add_sync_process(test)

        with sim.write_vcd("vcd/ds_input_data_char_sr.vcd", "gtkw/ds_input_data_char_sr.gtkw", traces=sr.ports()):
            sim.run()

    def test_output_sr():
        i_reset = Signal()
        i_input = Signal(10)
        i_send_data = Signal()
        i_send_control = Signal()
        m = Module()
        m.submodules.sr = sr = DSOutputCharSR()
        m.d.comb += [
            sr.i_input.eq(i_input),
            sr.i_send_control.eq(i_send_control),
            sr.i_send_data.eq(i_send_data),
            sr.i_reset.eq(i_reset)
        ]

        sim = Simulator(m)

        def test():
            yield
            yield
            yield
            yield i_input.eq(5)
            yield i_send_control.eq(1)
            yield
            yield
            yield i_send_control.eq(0)
            yield
            yield
            yield i_input.eq(178)
            yield i_send_data.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield i_send_data.eq(0)
            yield
            yield
            yield
            yield
            yield
            yield
            yield
            yield i_input.eq(879)
            yield i_send_data.eq(1)
            yield
            yield
            yield i_send_data.eq(0)
            yield
            yield
            yield
            yield i_reset.eq(1)
            yield
            yield
            yield
            yield
            yield i_reset.eq(0)
            yield
            yield
            yield

        sim.add_clock(1e-6)
        sim.add_sync_process(test)

        with sim.write_vcd("vcd/ds_output_char_sr.vcd", "gtkw/ds_output_char_sr.gtkw", traces=sr.ports()):
            sim.run()

    test_base_sr()
    test_control_sr()
    test_data_sr()
    test_output_sr()
