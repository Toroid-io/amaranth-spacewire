import enum
from nmigen import *
from nmigen.lib.fifo import SyncFIFOBuffered
from nmigen.sim import Simulator
from .spw_transmitter import SpWTransmitter
from .spw_receiver import SpWReceiver
from .spw_delay import SpWDelay
from .spw_sim_utils import *
import math
from nmigen_boards.de0_nano import DE0NanoPlatform


class SpWNodeFSMStates(enum.Enum):
    ERROR_RESET = 0
    ERROR_WAIT = 1
    READY = 2
    STARTED = 3
    CONNECTING = 4
    RUN = 5


class SpWNode(Elaboratable):
    def __init__(self, srcfreq, txfreq, transission_delay=12.8e-6, disconnect_delay=850e-9, time_master=True, debug=False):
        self.i_reset = Signal()
        self.i_switch_to_user_tx_freq = Signal()
        self.i_d = Signal()
        self.i_s = Signal()
        self.i_link_disabled = Signal()
        self.i_link_start = Signal()
        self.i_autostart = Signal()
        self.i_tick = Signal()
        self.o_tick = Signal()
        self.o_time_flags = Signal(2)
        self.o_time = Signal(6)
        self.o_link_error = Signal()
        self.o_d = Signal()
        self.o_s = Signal()

        # FIFO
        self.i_r_en = Signal()
        self.o_r_data = Signal(8)
        self.o_r_rdy = Signal()
        self.i_w_en = Signal()
        self.i_w_data = Signal(8)
        self.o_w_rdy = Signal()

        self._srcfreq = srcfreq
        self._txfreq = txfreq
        self._transission_delay = transission_delay
        self._disconnect_delay = disconnect_delay
        self._time_master = time_master

        self._debug = debug
        if debug:
            self.o_debug_rx_got_null = Signal()
            self.o_debug_rx_got_fct = Signal()
            self.o_debug_fsm_state = Signal(SpWNodeFSMStates)
            self.debug_tr = None

    def elaborate(self, platform):
        m = Module()

        m.submodules.tr = tr = SpWTransmitter(self._srcfreq, self._txfreq, debug=True)
        m.submodules.rx = rx = SpWReceiver(self._srcfreq, self._disconnect_delay)
        m.submodules.delay = delay = SpWDelay(self._srcfreq, self._transission_delay, strategy='at_least')

        use_user_tx_freq = Signal()
        tr_pre_send = Signal()
        rx_error = Signal()
        rx_tokens_count = Signal(range(7 + 1), reset=7)
        rx_read_counter = Signal(range(8))
        tx_credit = Signal(range(56 + 1))
        tx_credit_error = Signal()
        read_in_progress = Signal()
        gotNULL = Signal()
        time_counter = Signal(6)
        time_updated = Signal()
        link_enabled = Signal()

        m.d.comb += [
            self.o_d.eq(tr.o_d),
            self.o_s.eq(tr.o_s),
            rx.i_d.eq(self.i_d),
            rx.i_s.eq(self.i_s),
            rx_error.eq(rx.o_escape_error | rx.o_parity_error | rx.o_read_error | rx.o_disconnect_error),
            link_enabled.eq(~self.i_link_disabled & (self.i_link_start | (self.i_autostart & gotNULL))),
            tr.i_switch_to_user_tx_freq.eq(use_user_tx_freq)
        ]

        m.submodules.rx_fifo = rx_fifo = SyncFIFOBuffered(width=8, depth=56)
        m.submodules.tx_fifo = tx_fifo = SyncFIFOBuffered(width=8, depth=56)

        m.d.comb += [
            rx_fifo.r_en.eq(self.i_r_en),
            self.o_r_data.eq(rx_fifo.r_data),
            self.o_r_rdy.eq(rx_fifo.r_rdy),
            rx_fifo.w_data.eq(rx.o_data_char),

            tx_fifo.w_en.eq(self.i_w_en),
            tx_fifo.w_data.eq(self.i_w_data),
            self.o_w_rdy.eq(tx_fifo.w_rdy),

            read_in_progress.eq(self.i_r_en & rx_fifo.r_rdy)
        ]

        with m.FSM() as main_fsm:
            with m.State(SpWNodeFSMStates.ERROR_RESET):
                m.d.comb += rx.i_reset.eq(1)
                m.d.comb += tr.i_reset.eq(1)
                m.d.sync += [
                    rx_tokens_count.eq(7),
                    tx_credit.eq(0),
                    gotNULL.eq(0),
                ]

                with m.If(self.i_reset):
                    pass
                with m.Elif(delay.o_half_elapsed):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_WAIT
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State(SpWNodeFSMStates.ERROR_WAIT):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(1)

                with m.If((rx_error | (gotNULL & (rx.o_got_fct | rx.o_got_data | rx.o_got_timecode))) == 1):
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

                with m.If((rx_error | (gotNULL & (rx.o_got_fct | rx.o_got_data | rx.o_got_timecode))) == 1):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_RESET
                with m.Elif(link_enabled == 1):
                    m.next = SpWNodeFSMStates.STARTED
                with m.Elif(rx.o_got_null):
                    m.d.sync += gotNULL.eq(1)
            with m.State(SpWNodeFSMStates.STARTED):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(0)

                with m.If((rx_error | (gotNULL & (rx.o_got_fct | rx.o_got_data | rx.o_got_timecode)) | delay.o_elapsed) == 1):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_RESET
                with m.Elif((gotNULL | rx.o_got_null) == 1):
                    m.d.sync += gotNULL.eq(1)
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.CONNECTING
                with m.Else():
                    m.d.comb += delay.i_start.eq(1)
            with m.State(SpWNodeFSMStates.CONNECTING):
                m.d.comb += rx.i_reset.eq(0)
                m.d.comb += tr.i_reset.eq(0)
                m.d.comb += tr.i_send_fct.eq((rx_tokens_count > 0) & (tr.o_ready == 1))

                with m.If((rx_error | rx.o_got_data | rx.o_got_timecode | delay.o_elapsed) == 1):
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

                with m.If((rx_error | tx_credit_error | self.i_link_disabled) == 1):
                    m.d.comb += delay.i_reset.eq(1)
                    m.next = SpWNodeFSMStates.ERROR_RESET
                with m.Else():
                    m.d.comb += rx_fifo.w_en.eq(rx.o_got_data)
                    with m.If(time_updated & tr.o_ready):
                        m.d.comb += [
                            tr.i_send_time.eq(1),
                            tr.i_char.eq(time_counter)
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
            with m.Elif(rx.o_got_fct & (tx_credit > (56 - 8))):
                m.d.comb += tx_credit_error.eq(1)
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
        m.d.comb += self.o_link_error.eq(main_fsm.ongoing(SpWNodeFSMStates.RUN) & (rx_error | tx_credit_error))

        # Time management
        with m.If(self.i_reset):
            m.d.sync += time_counter.eq(0)
        with m.Elif(self.i_tick & self._time_master):
            m.d.sync += [time_counter.eq(time_counter + 1), time_updated.eq(1)]
        with m.Elif(tr.i_send_time):
            m.d.sync += time_updated.eq(0)
        with m.Elif(rx.o_got_timecode & (not self._time_master)):
            with m.If(rx.o_data_char[0:6] == (time_counter + 1)):
                # Output tick + store flags + store counter
                m.d.sync += [
                    self.o_tick.eq(1),
                    self.o_time.eq(time_counter + 1),
                    self.o_time_flags.eq(rx.o_data_char[6:8]),
                    time_counter.eq(time_counter + 1)
                ]
            with m.Elif(rx.o_data_char[0:6] != time_counter):
                m.d.sync += time_counter.eq(rx.o_data_char[0:6])
        with m.Else():
            m.d.sync += self.o_tick.eq(0)

        # User TX Frequency management
        with m.If(main_fsm.ongoing(SpWNodeFSMStates.RUN) & self.i_switch_to_user_tx_freq & tr.o_ready):
            m.d.sync += use_user_tx_freq.eq(1)
        with m.Elif(~main_fsm.ongoing(SpWNodeFSMStates.RUN) | ~self.i_switch_to_user_tx_freq & tr.o_ready):
            m.d.sync += use_user_tx_freq.eq(0)

        if self._debug:
            m.d.comb += [
                self.o_debug_rx_got_null.eq(rx.o_got_null),
                self.o_debug_rx_got_fct.eq(rx.o_got_fct),
                self.o_debug_fsm_state.eq(main_fsm.state)
            ]
            self.debug_tr = tr

        return m

    def ports(self):
        return [
            self.i_reset, self.i_d, self.i_s, self.i_link_disabled,
            self.i_link_start, self.i_autostart, self.i_tick, self.o_tick,
            self.o_time_flags, self.o_time, self.o_link_error, self.o_d,
            self.o_s, self.o_r_data, self.o_r_rdy, self.i_w_en, self.i_w_data,
            self.o_w_rdy
        ]


if __name__ == '__main__':
    srcfreq = 50e6
    linkfreq = 45e6
    i_link_disable = Signal()
    i_autostart = Signal(reset=1)
    i_link_start = Signal(reset=1)
    i_tick = Signal()
    m = Module()
    m.submodules.fsm = fsm = SpWNode(srcfreq, linkfreq)
    m.d.comb += [
        fsm.i_link_disabled.eq(i_link_disable),
        fsm.i_link_start.eq(i_link_start),
        fsm.i_autostart.eq(i_autostart),
        fsm.i_tick.eq(i_tick),
        fsm.i_d.eq(fsm.o_d),
        fsm.i_s.eq(fsm.o_s)
    ]

    sim = Simulator(m)
    sim.add_clock(1/srcfreq)

    def test():
        for _ in range(ds_sim_period_to_ticks(25e-6, srcfreq)):
            yield
        for _ in range(ds_sim_period_to_ticks(30e-6, srcfreq)):
            yield
        for i in range(40):
            yield fsm.i_w_en.eq(1)
            yield fsm.i_w_data.eq(ord('A')+i)
            yield
        yield fsm.i_w_en.eq(0)
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
            if (yield fsm.o_r_rdy):
                yield fsm.i_r_en.eq(1)
            else:
                yield fsm.i_r_en.eq(0)
            yield

    sim.add_sync_process(test)
    sim.add_sync_process(read_from_fifo)
    sim.add_sync_process(tick_process)
    with sim.write_vcd("vcd/spw_node.vcd", "gtkw/spw_node.gtkw", traces=fsm.ports()):
        sim.run_until(1200e-6)