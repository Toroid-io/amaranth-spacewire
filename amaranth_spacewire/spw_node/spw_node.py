import enum
import math

from amaranth import *
from amaranth.lib.fifo import SyncFIFOBuffered
from amaranth.sim import Simulator
from .spw_transmitter import SpWTransmitter, SpWTransmitterStates
from .spw_receiver import SpWReceiver
from .spw_delay import SpWDelay
from .spw_sim_utils import *
from amaranth_boards.de0_nano import DE0NanoPlatform


class SpWNodeFSMStates(enum.Enum):
    ERROR_RESET = 0
    ERROR_WAIT = 1
    READY = 2
    STARTED = 3
    CONNECTING = 4
    RUN = 5


class SpWNode(Elaboratable):
    def __init__(self, srcfreq, txfreq, transission_delay=12.8e-6, disconnect_delay=850e-9, time_master=True, rx_tokens=7, tx_tokens=7, debug=False):
        # Data/Strobe
        self.d_input = Signal()
        self.s_input = Signal()
        self.d_output = Signal()
        self.s_output = Signal()

        # Time functions
        self.tick_input = Signal()
        self.tick_output = Signal()
        self.time_flags = Signal(2)
        self.time_value = Signal(6)

        # FIFO
        self.r_en = Signal()
        self.r_data = Signal(8)
        self.r_rdy = Signal()
        self.w_en = Signal()
        self.w_data = Signal(8)
        self.w_rdy = Signal()

        # Status signals
        self.link_state = Signal(SpWNodeFSMStates)
        self.link_error = Signal()

        # Control signals
        self.soft_reset = Signal()
        self.switch_to_user_tx_freq = Signal()
        self.link_disabled = Signal()
        self.link_start = Signal()
        self.autostart = Signal()
        self.link_error_clear = Signal()
        self.link_autorecover = Signal()

        self._srcfreq = srcfreq
        self._txfreq = txfreq
        self._transission_delay = transission_delay
        self._disconnect_delay = disconnect_delay
        self._time_master = Const(1 if time_master else 0)
        self._rx_tokens = rx_tokens
        self._tx_tokens = tx_tokens

        self._debug = debug
        if debug:
            self.o_debug_rx_got_null = Signal()
            self.o_debug_rx_got_fct = Signal()
            self.debug_tr = None
            self.o_debug_time_counter = Signal(6)
            self.o_debug_tr_send_time = Signal()
            self.o_debug_tr_fsm_state = Signal(SpWTransmitterStates)
            self.o_debug_tr_sr_input = Signal(8)

    def elaborate(self, platform):
        m = Module()

        m.submodules.tr = tr = SpWTransmitter(self._srcfreq, self._txfreq, debug=True)
        m.submodules.rx = rx = SpWReceiver(self._srcfreq, self._disconnect_delay)
        m.submodules.delay = delay = SpWDelay(self._srcfreq, self._transission_delay, strategy='at_least')

        use_user_tx_freq = Signal()
        tr_pre_send = Signal()
        rx_error = Signal()
        rx_tokens_count = Signal(range(self._rx_tokens + 1), reset=self._rx_tokens)
        rx_read_counter = Signal(range(8))
        tx_credit = Signal(range(8 * self._tx_tokens + 1))
        tx_credit_error = Signal()
        read_in_progress = Signal()
        gotNULL = Signal()
        sentNULL = Signal()
        time_counter = Signal(6)
        time_updated = Signal()
        link_enabled = Signal()

        m.d.comb += [
            self.d_output.eq(tr.o_d),
            self.s_output.eq(tr.o_s),
            rx.i_d.eq(self.d_input),
            rx.i_s.eq(self.s_input),
            rx_error.eq(rx.o_escape_error | rx.o_parity_error | rx.o_read_error | rx.o_disconnect_error),
            link_enabled.eq(~self.link_disabled & (self.link_start | (self.autostart & gotNULL))),
            tr.i_switch_to_user_tx_freq.eq(use_user_tx_freq)
        ]

        m.submodules.rx_fifo = rx_fifo = SyncFIFOBuffered(width=8, depth=8 * self._rx_tokens)
        m.submodules.tx_fifo = tx_fifo = SyncFIFOBuffered(width=8, depth=8 * self._tx_tokens)

        m.d.comb += [
            rx_fifo.r_en.eq(self.r_en),
            self.r_data.eq(rx_fifo.r_data),
            self.r_rdy.eq(rx_fifo.r_rdy),
            rx_fifo.w_data.eq(rx.o_data_char),

            tx_fifo.w_en.eq(self.w_en),
            tx_fifo.w_data.eq(self.w_data),
            self.w_rdy.eq(tx_fifo.w_rdy),

            read_in_progress.eq(self.r_en & rx_fifo.r_rdy)
        ]

        with m.FSM() as main_fsm:
            with m.State(SpWNodeFSMStates.ERROR_RESET):
                m.d.comb += rx.i_reset.eq(1)
                m.d.comb += tr.i_reset.eq(1)
                m.d.sync += [
                    rx_tokens_count.eq(self._rx_tokens),
                    rx_read_counter.eq(0),
                    tx_credit.eq(0),
                    tx_credit_error.eq(0),
                    gotNULL.eq(0),
                    sentNULL.eq(0),
                    time_counter.eq(0),
                    self.time_value.eq(0),
                    self.time_flags.eq(0),
                    time_updated.eq(0)
                ]

                with m.If(self.soft_reset | (self.link_error & ~self.link_autorecover)):
                    m.d.comb += delay.i_reset.eq(1)
                with m.Elif(delay.o_half_elapsed):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_WAIT
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State(SpWNodeFSMStates.ERROR_WAIT):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(1)

                with m.If(self.soft_reset | rx_error | (gotNULL & (rx.o_got_fct | rx.o_got_data | rx.o_got_timecode))):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_RESET
                with m.Elif(delay.o_elapsed == 1):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.READY
                with m.Elif(rx.o_got_null):
                    m.d.sync += gotNULL.eq(1)
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State(SpWNodeFSMStates.READY):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(1)

                with m.If(self.soft_reset | rx_error | (gotNULL & (rx.o_got_fct | rx.o_got_data | rx.o_got_timecode))):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_RESET
                with m.Elif(link_enabled == 1):
                    m.next = SpWNodeFSMStates.STARTED
                with m.Elif(rx.o_got_null):
                    m.d.sync += gotNULL.eq(1)
            with m.State(SpWNodeFSMStates.STARTED):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(0)
                m.d.sync += sentNULL.eq(tr.o_ready | sentNULL)

                with m.If(self.soft_reset | rx_error | (gotNULL & (rx.o_got_fct | rx.o_got_data | rx.o_got_timecode)) | delay.o_elapsed):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_RESET
                with m.Elif(gotNULL | rx.o_got_null):
                    m.d.sync += gotNULL.eq(1)
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.CONNECTING
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State(SpWNodeFSMStates.CONNECTING):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(0)
                m.d.comb += tr.i_send_fct.eq((rx_tokens_count > 0) & (tr.o_ready == 1) & sentNULL)
                m.d.sync += sentNULL.eq(tr.o_ready | sentNULL)

                with m.If(self.soft_reset | rx_error | rx.o_got_data | rx.o_got_timecode | delay.o_elapsed):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_RESET
                with m.Elif(rx.o_got_fct == 1):
                    m.d.sync += tx_credit.eq(tx_credit + 8)
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.RUN
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State(SpWNodeFSMStates.RUN):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(0)
                m.d.comb += tr_pre_send.eq((tx_fifo.level > 0) & tr.o_ready & (tx_credit > 0) & tx_fifo.r_rdy)

                with m.If(self.soft_reset | rx_error | tx_credit_error | self.link_disabled):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_RESET
                with m.Else():
                    m.d.comb += rx_fifo.w_en.eq(rx.o_got_data)
                    with m.If(time_updated & tr.o_ready):
                        m.d.comb += [
                            tr.i_send_time.eq(1),
                            tr.i_char.eq(Cat(time_counter, Const(0, 2)))
                        ]
                    with m.Elif((rx_tokens_count > 0) & (tr.o_ready == 1)):
                        m.d.comb += tr.i_send_fct.eq(1)
                    with m.Else():
                        m.d.comb += [
                            tx_fifo.r_en.eq(tr_pre_send),
                            tr.i_char.eq(tx_fifo.r_data),
                            tr.i_send_char.eq(tr_pre_send),
                        ]

        # Tokens and credit management
        with m.If(main_fsm.ongoing(SpWNodeFSMStates.CONNECTING) | main_fsm.ongoing(SpWNodeFSMStates.RUN)):
            with m.If(tr.i_send_char & ~rx.o_got_fct):
                m.d.sync += tx_credit.eq(tx_credit - 1)
            with m.Elif(rx.o_got_fct & (tx_credit > (8 * self._tx_tokens - 8))):
                m.d.sync += tx_credit_error.eq(1)
            with m.Elif(rx.o_got_fct & ~tr.i_send_char):
                m.d.sync += tx_credit.eq(tx_credit + 8)
            with m.Elif(rx.o_got_fct & tr.i_send_char):
                m.d.sync += tx_credit.eq(tx_credit + 7)

            with m.If(read_in_progress):
                m.d.sync += rx_read_counter.eq(rx_read_counter + 1)

            with m.If(read_in_progress & ~tr.i_send_fct):
                with m.If(rx_read_counter == 7):
                    m.d.sync += rx_tokens_count.eq(rx_tokens_count + 1)
            with m.Elif(~read_in_progress & tr.i_send_fct):
                m.d.sync += rx_tokens_count.eq(rx_tokens_count - 1)
            with m.If(read_in_progress & tr.i_send_fct):
                with m.If(~(rx_read_counter == 7)):
                    m.d.sync += rx_tokens_count.eq(rx_tokens_count - 1)

        # Link error
        with m.If(self.soft_reset | self.link_error_clear):
            m.d.sync += self.link_error.eq(0)
        with m.Elif(main_fsm.ongoing(SpWNodeFSMStates.RUN) & (rx_error | tx_credit_error)):
            m.d.sync += self.link_error.eq(1)

        # Time management
        with m.If(~self.soft_reset & self._time_master):
            with m.If(self.tick_input):
                m.d.sync += [time_counter.eq(time_counter + 1), time_updated.eq(1)]
            with m.Elif(tr.i_send_time):
                m.d.sync += time_updated.eq(0)
        with m.Elif(~self.soft_reset):
            with m.If(rx.o_got_timecode):
                with m.If(rx.o_data_char[0:6] == (time_counter + 1)):
                    # Output tick + store flags + store counter
                    m.d.comb += self.tick_output.eq(1)
                    m.d.sync += [
                        self.time_value.eq(time_counter + 1),
                        self.time_flags.eq(rx.o_data_char[6:8]),
                        time_counter.eq(time_counter + 1)
                    ]
                with m.Elif(rx.o_data_char[0:6] != time_counter):
                    m.d.sync += time_counter.eq(rx.o_data_char[0:6])

        # User TX Frequency management
        with m.If(main_fsm.ongoing(SpWNodeFSMStates.RUN) & self.switch_to_user_tx_freq & tr.o_ready):
            m.d.sync += use_user_tx_freq.eq(1)
        with m.Elif(~main_fsm.ongoing(SpWNodeFSMStates.RUN) | ~self.switch_to_user_tx_freq & tr.o_ready):
            m.d.sync += use_user_tx_freq.eq(0)

        m.d.comb += self.link_state.eq(main_fsm.state)

        if self._debug:
            m.d.comb += [
                self.o_debug_rx_got_null.eq(rx.o_got_null),
                self.o_debug_rx_got_fct.eq(rx.o_got_fct),
                self.o_debug_time_counter.eq(time_counter),
                self.o_debug_tr_send_time.eq(tr.i_send_time),
                self.o_debug_tr_fsm_state.eq(tr.o_debug_fsm_state),
                self.o_debug_tr_sr_input.eq(tr.o_debug_sr_input)
            ]
            self.debug_tr = tr

        return m

    def ports(self):
        return [
            self.soft_reset, self.d_input, self.s_input, self.link_disabled,
            self.link_start, self.autostart, self.tick_input, self.tick_output,
            self.time_flags, self.time_value, self.link_error, self.d_output,
            self.s_output, self.r_en, self.r_data, self.r_rdy, self.w_en, self.w_data,
            self.w_rdy, self.switch_to_user_tx_freq, self.link_state, self.link_error_clear,
            self.link_autorecover
        ]


if __name__ == '__main__':
    srcfreq = 50e6
    linkfreq = 25e6
    i_link_disable = Signal()
    i_autostart = Signal(reset=1)
    i_link_start = Signal(reset=1)
    i_tick = Signal()
    m = Module()
    m.submodules.fsm = fsm = SpWNode(srcfreq, linkfreq)
    m.d.comb += [
        fsm.link_disabled.eq(i_link_disable),
        fsm.link_start.eq(i_link_start),
        fsm.autostart.eq(i_autostart),
        fsm.tick_input.eq(i_tick),
        fsm.d_input.eq(fsm.d_output),
        fsm.s_input.eq(fsm.s_output)
    ]

    sim = Simulator(m)
    sim.add_clock(1/srcfreq)

    def test():
        for _ in range(ds_sim_period_to_ticks(25e-6, srcfreq)):
            yield
        for _ in range(ds_sim_period_to_ticks(30e-6, srcfreq)):
            yield
        for i in range(40):
            yield fsm.w_en.eq(1)
            yield fsm.w_data.eq(ord('A')+i)
            yield
        yield fsm.w_en.eq(0)
        for _ in range(ds_sim_period_to_ticks(100e-6, srcfreq)):
            yield

    def tick_process():
        for _ in range(math.ceil(500e-6/15e-6)):
            for _ in range(ds_sim_period_to_ticks(15e-6, srcfreq)):
                yield
            yield i_tick.eq(1)
            yield
            yield i_tick.eq(0)
            yield

    def read_from_fifo():
        for _ in range(ds_sim_period_to_ticks(400e-6, srcfreq)):
            yield
        while True:
            if (yield fsm.r_rdy):
                yield fsm.r_en.eq(1)
            else:
                yield fsm.r_en.eq(0)
            yield

    sim.add_sync_process(test)
    sim.add_sync_process(read_from_fifo)
    sim.add_sync_process(tick_process)
    with sim.write_vcd("vcd/spw_node.vcd", "gtkw/spw_node.gtkw", traces=fsm.ports()):
        sim.run_until(1200e-6)
