import enum

from amaranth import *
from amaranth_spacewire.misc.spw_delay import SpWDelay
from amaranth_spacewire.misc.states import DataLinkState, RecoveryState


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
        self.read_error = Signal()
        self.disconnect_error = Signal()
        self.parity_error = Signal()
        self.esc_error = Signal()
        self.credit_error = Signal()
        self.link_state = Signal(DataLinkState)
        self.recovery_state = Signal(RecoveryState)

        ## Ports: Signals for the MIB
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
                with m.If(self.link_disabled | (self.recovery_state != RecoveryState.NORMAL)):
                    m.d.comb += delay.i_start.eq(0)
                with m.Elif(delay.o_half_elapsed):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_WAIT
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

            with m.State(DataLinkState.ERROR_WAIT):
                with m.If(self.disconnect_error | self.parity_error
                          | self.esc_error | gotFCT
                          | self.got_n_char | self.got_bc
                          | self.link_disabled | self.read_error):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
                with m.Elif(delay.o_elapsed == 1):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.READY
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

            with m.State(DataLinkState.READY):
                with m.If(self.disconnect_error | self.parity_error
                          | self.esc_error | gotFCT
                          | self.got_n_char | self.got_bc
                          | self.link_disabled | self.read_error):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
                with m.Elif(self.link_start | (self.autostart & gotNULL)):
                    m.next = DataLinkState.STARTED

            with m.State(DataLinkState.STARTED):
                with m.If(self.disconnect_error | self.parity_error
                          | self.esc_error | gotFCT
                          | self.got_n_char | self.got_bc
                          | self.link_disabled | self.read_error
                          | delay.o_elapsed):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
                with m.Elif(gotNULL & sentNULL):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.CONNECTING
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

            with m.State(DataLinkState.CONNECTING):
                with m.If(self.disconnect_error | self.parity_error
                          | self.esc_error | self.got_n_char
                          | self.got_bc | self.link_disabled
                          | self.read_error | delay.o_elapsed):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.ERROR_RESET
                with m.Elif(gotFCT & sentFCT):
                    m.d.comb += delay.i_start.eq(0)
                    m.next = DataLinkState.RUN
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)

            with m.State(DataLinkState.RUN):
                with m.If(self.disconnect_error | self.parity_error
                          | self.esc_error | self.credit_error
                          | self.link_disabled | self.read_error):
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
            self.read_error,
            self.credit_error,
            self.sent_null,
            self.link_state,
            self.link_disabled,
            self.link_start,
            self.autostart,
        ]