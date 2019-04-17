#!/usr/bin/env python

"""PTP Simulator

Conventions:
- Simulation time is given in seconds
- RTC time is kept in seconds/nanoseconds
- Message periods are in seconds
- units are explicit within variable names where possible

"""
import argparse, logging, sys, random, math, heapq
import numpy as np

class TimeReg():
    def __init__(self, sec_0 = 0, ns_0 = 0):
        """Time-keeping Second/Nanosecond Registers

        Args:
        sec_0 : Initial seconds value
        ns_0  : Initial nanoseconds value
        """
        self.sec = int(sec_0)
        self.ns  = float(ns_0)

    def __str__(self):
        """Print sec and ns values"""
        return '{} sec, {} ns'.format(self.sec, self.ns)

    def add(self, delta_ns):
        """Add an interval to the time count

        Args:
            delta_ns : interval in nanoseconds
        """

        self.sec += math.floor((self.ns + delta_ns)/1e9);
        self.ns   = (self.ns + delta_ns) % 1e9

        assert(isinstance(self.sec, int))
        assert(isinstance(self.ns, float))
        assert(self.sec >= 0)
        assert(self.ns >= 0)


class Rtc():
    def __init__(self, clk_freq_hz, resolution_ns, label):
        """Real-time Clock (RTC)

        Args:
        clk_freq_hz   : Frequency (in Hz) of the driving clock signal
        resolution_ns : Timestamp resolution in nanoseconds
        label         : RTC label
        """

        # Start the rtc with a random time and phase
        sec_0 = random.randint(0, 1000)
        ns_0  = random.uniform(0, 1e9)

        # Nominal increment value in nanoseconds
        inc_val_ns = (1.0/clk_freq_hz)*1e9

        # The phase is the instant within the period of the driving clock signal
        # where the rising edge is located
        phase_0_ns = random.uniform(0, inc_val_ns)

        self.inc_cnt    = 0
        self.freq_hz    = clk_freq_hz  # driving clock signal freq.
        self.period_ns  = inc_val_ns   # driving clock signal period
        self.inc_val_ns = inc_val_ns   # increment value
        self.phase_ns   = phase_0_ns   # phase
        self.time       = TimeReg(sec_0, ns_0)
        self.toffset    = TimeReg()
        self.label      = label

        logger = logging.getLogger('Rtc')
        logger.debug("Initialized the %s RTC" %(self.label))
        logger.debug("%-16s\t %f ns" %("Increment value:", self.inc_val_ns))
        logger.debug("%-16s\t %f ns" %("Initial phase:", self.phase_ns))
        logger.debug("%-16s\t %s" %("Initial time:", self.time))

    def update(self, t_sim):
        """Update the RTC time

        Args:
            t_sim : simulation time in seconds
        """

        t_sim_ns = t_sim * 1e9

        # Check how many times the RTC has incremented so far:
        n_incs = math.floor((t_sim_ns - self.phase_ns) / (self.period_ns))

        # Prevent negative number of increments
        if (n_incs < 0):
            n_incs = 0

        # Track the number of increments that haven't been taken into account
        # yet
        new_incs = n_incs - self.inc_cnt

        # Elapsed time at the RTC since last update:
        elapsed_ns = new_incs * self.inc_val_ns
        # NOTE: the elapsed time depends on the increment value that is
        # currently configured at the RTC. The number of increments, in
        # contrast, does not depend on the current RTC configuration.

        # Update the increment counter
        self.inc_cnt = n_incs

        # Update the RTC seconds count:
        self.time.add(elapsed_ns)

        logger = logging.getLogger('Rtc')
        logger.debug("[%-6s] Simulation time: %f ns" %(self.label, t_sim_ns))
        logger.debug("[%-6s] Advance RTC by %u ns" %(self.label, elapsed_ns))
        logger.debug("[%-6s] New RTC time: %s" %(self.label, self.time))

    def get_time(self):
        """Get current RTC time
        """
        return self.time


class PtpEvt():
    def __init__(self, name, period_sec=None):
        """PTP Event Message

        Controls transmission and reception of a PTP event message. When the
        message is periodically transmitted (Sync), a period must be passed by
        argument. Otherwise, transmission must be scheduled manually.

        Args:
            name       : Message name
            period_sec : Transmission period in seconds

        """

        self.name       = name
        self.period_sec = period_sec
        self.on_way     = False
        self.next_tx    = float("inf")
        self.next_rx    = float("inf")
        self.seq_num    = 0

    def _sched_next_tx(self, tx_sim_time):
        """Compute next transmission time for periodic message

        Args:
            tx_sim_time : Simulation time (secs) corresponding to the Tx instant

        """

        self.next_tx = tx_sim_time + self.period_sec
        # TODO model message interval uncertainty

    def _sched_rx(self, tx_sim_time):
        """Schedule Reception

        Args:
            tx_sim_time : Simulation time (secs) corresponding to the Tx instant

        """

        delay_ns     = np.random.gamma(shape=2, scale=1000)
        # FIXME set Gamma params

        self.next_rx = tx_sim_time + (delay_ns * 1e-9)

        logger = logging.getLogger("PtpEvt")
        logger.debug("Delay of %s #%d: %f ns" %(self.name, self.seq_num, delay_ns))

    def sched_tx(self, tx_sim_time, evts):
        """Manually schedule a transmission time

        Args:
            tx_sim_time : Target simulation time (secs) for Tx
            evts        : Event heap queue

        """
        self.next_tx = tx_sim_time
        heapq.heappush(evts, self.next_tx)

    def tx(self, sim_time, rtc_timestamp, evts):
        """Transmit message

        Args:
            sim_time      : Simulation time in seconds
            rtc_timestamp : RTC Time
            evts          : Event heap queue

        """

        # Do not transmit before scheduled time or if there is already an
        # ongoing transmission
        if ((sim_time < self.next_tx) or self.on_way):
            return

        # Proceed with transmission
        self.on_way         = True
        self.tx_tstamp      = rtc_timestamp
        self.seq_num       += 1

        logger = logging.getLogger("PtpEvt")
        logger.debug("Transmitting %s at %s" %(self.name, sim_time))

        # Schedule the next transmission for periodic messages
        if (self.period_sec is not None):
            self._sched_next_tx(sim_time)
            heapq.heappush(evts, self.next_tx)

        # Schedule the reception
        self._sched_rx(sim_time)
        heapq.heappush(evts, self.next_rx)

    def rx(self, sim_time, rtc_timestamp):
        """Receive Message

        Args:
            sim_time      : Simulation time in seconds
            rtc_timestamp : RTC Time

        Returns:
            True when effectively received
        """

        # Do not receive before scheduled time or if there isn't a message on
        # the way
        if ((sim_time < self.next_rx) or (not self.on_way)):
            return False

        # Proceed with reception
        self.on_way         = False
        self.rx_tstamp      = rtc_timestamp

        logger = logging.getLogger("PtpEvt")
        logger.debug("Received %s at %s" %(self.name, sim_time))

        return True

class SimTime():
    def __init__(self, t_step):
        """Simulation Time

        Keeps track of simulation time in seconds

        Args:
            t_step : Simulation time step in seconds
        """
        self.time   = 0
        self.t_step = t_step

    def get_time(self):
        """Return the simulation time"""
        return self.time

    def advance(self, next_time):
        """Advance simulation time to a specified instant"""
        self.time = next_time
        logger = logging.getLogger("SimTime")
        logger.debug("Advance simulation time to: %f ns" %(self.time))

    def step(self):
        """Advance simulation time by the simulation step"""
        self.time += self.t_step


def run(n_iter, sim_t_step):
    """Main loop

    Args:
        n_iter        : Number of iterations
        sim_t_step    : Simulation time step in seconds
    """

    # Constants
    sync_period    = 1.0/16 # in seconds
    rtc_clk_freq   = 125e6  # in Hz
    rtc_resolution = 0 # TODO

    # Register the PTP message objects
    sync = PtpEvt("Sync", sync_period)
    dreq = PtpEvt("Delay_Req")

    # RTCs
    master_rtc = Rtc(rtc_clk_freq, rtc_resolution, "Master")
    slave_rtc  = Rtc(rtc_clk_freq, rtc_resolution, "Slave")

    # Simulation time
    sim_timer = SimTime(sim_t_step)

    # Main loop
    evts     = list()
    stop     = False
    i_msg    = 0

    # Start with a sync transmission
    sync.next_tx = 0

    while (not stop):
        sim_time = sim_timer.get_time()

        # Update the RTCs
        master_rtc.update(sim_time)
        slave_rtc.update(sim_time)

        # Try processing all events
        sync.tx(sim_time, master_rtc.get_time(), evts)
        sync_received = sync.rx(sim_time, slave_rtc.get_time())
        dreq.tx(sim_time, slave_rtc.get_time(), evts)
        dreq.rx(sim_time, master_rtc.get_time())

        # Schedule the transmissions that need to be set manually:
        if (sync_received):
            dreq.sched_tx(sim_time, evts)

        # Message exchange count
        i_msg += 1

        # Update simulation time
        if (len(evts) > 0):
            next_evt = heapq.heappop(evts)
            sim_timer.advance(next_evt)
        else:
            sim_timer.step()

        # Stop criterion
        if (i_msg >= n_iter):
            stop = True


def main():
    parser = argparse.ArgumentParser(description="PTP Simulator")
    parser.add_argument('-N', '--num-iter',
                        default=10,
                        type=int,
                        help='Number of iterations.')
    parser.add_argument('-t', '--sim-step',
                        default=1e-9,
                        type=float,
                        help='Simulation time step in seconds.')
    parser.add_argument('--debug', action='store_true', help='Debug mode.')
    args     = parser.parse_args()
    num_iter = args.num_iter
    sim_step = args.sim_step

    if (args.debug):
        logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
        logging.debug('[Debug Mode]')

    run(num_iter, sim_step)

if __name__ == "__main__":
    main()
