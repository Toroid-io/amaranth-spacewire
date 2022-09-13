import enum

from amaranth import *
from amaranth_spacewire.misc.spw_delay import SpWDelay


class DataLinkState(enum.Enum):
    ERROR_RESET = 0
    ERROR_WAIT = 1
    READY = 2
    STARTED = 3
    CONNECTING = 4
    RUN = 5


class DataLinkFSM(Elaboratable):
    def __init__(self,
                 srcfreq,
                 transission_delay=12.8e-6):

        # Ports
        ## Ports: Interface
        self.got_fct = Signal()
        self.sent_fct = Signal()
        self.got_n_char = Signal()
        self.got_null = Signal()
        self.sent_null = Signal()
        self.got_bc = Signal()
        self.receive_error = Signal()
        self.credit_error = Signal()
        self.link_state = Signal(DataLinkState)

        ## Ports: Signals for the MIB
        self.link_error_flags = Signal(4)
        self.link_disabled = Signal()
        self.link_start = Signal()
        self.autostart = Signal()

        # Internals
        self._srcfreq = srcfreq
        self._transission_delay = transission_delay

    
    def elaborate(self, platform):
        m = Module()
        
        m.submodules.delay = delay = SpWDelay(self._srcfreq, self._transission_delay, strategy='at_most')
        

        # Stay at 1 once the first null/fct is received/sent
        got_null_reg = Signal()
        sent_null_reg = Signal()
        got_fct_reg = Signal()
        sent_fct_reg = Signal()

        with m.If(self.link_state == DataLinkState.ERROR_RESET):
            m.d.sync += [
                got_null_reg.eq(0),
                sent_null_reg.eq(0),
                got_fct_reg.eq(0),
                sent_fct_reg.eq(0),
            ]
        with m.Else():
            m.d.sync += [
                got_null_reg.eq(got_null_reg | self.got_null),
                sent_null_reg.eq(sent_null_reg | self.sent_null),
                got_fct_reg.eq(got_fct_reg | self.got_fct),
                sent_fct_reg.eq(sent_fct_reg | self.sent_fct),
            ]
        
        # This lets the FSM react in the same clock cycle
        gotNULL = Signal()
        sentNULL = Signal()
        gotFCT = Signal()
        sentFCT = Signal()
        
        m.d.comb += [
            gotNULL.eq(got_null_reg | self.got_null),
            sentNULL.eq(sent_null_reg | self.sent_null),
            gotFCT.eq(got_fct_reg | self.got_fct),
            sentFCT.eq(sent_fct_reg | self.sent_fct),
        ]

        with m.FSM() as datalink_fsm:
            with m.State(DataLinkState.ERROR_RESET):
                with m.If(self.link_disabled):
                    m.d.comb += delay.i_start.eq(0)
                with m.Elif(delay.o_half_elapsed):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_WAIT
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

            with m.State(DataLinkState.ERROR_WAIT):
                with m.If(self.link_disabled | self.receive_error | gotFCT |
                        self.got_n_char | self.got_bc):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
                with m.Elif(delay.o_elapsed == 1):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.READY
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

            with m.State(DataLinkState.READY):
                with m.If(self.link_disabled | self.receive_error | gotFCT |
                        self.got_n_char | self.got_bc):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
                with m.Elif(self.link_start | (self.autostart & gotNULL)):
                    m.next = DataLinkState.STARTED

            with m.State(DataLinkState.STARTED):
                with m.If(self.link_disabled | self.receive_error | gotFCT |
                        self.got_n_char | self.got_bc | delay.o_elapsed):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
                with m.Elif(gotNULL & sentNULL):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.CONNECTING
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

            with m.State(DataLinkState.CONNECTING):
                with m.If(self.link_disabled | self.receive_error | self.got_n_char |
                        self.got_bc | delay.o_elapsed):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
                with m.Elif(gotFCT & sentFCT):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.RUN
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

            with m.State(DataLinkState.RUN):
                with m.If(self.link_disabled | self.receive_error | self.credit_error):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
        
        m.d.comb += self.link_state.eq(datalink_fsm.state)

        return m

    def ports(self):
        return [
            self.got_fct,
            self.sent_fct,
            self.got_n_char,
            self.got_null,
            self.got_bc,
            self.receive_error,
            self.credit_error,
            self.sent_null,
            self.link_state,
            self.link_disabled,
            self.link_start,
            self.autostart,
        ]