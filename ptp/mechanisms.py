"""PTP packet exchange mechanisms
"""
import logging
from .timestamping import *


class DelayReqResp():
    def __init__(self, seq_num, t1):
        """Delay request-response mechanism

        Args:
            seq_num : Sequence number
            t1      : Sync departure timestamp
        """
        self.seq_num   = seq_num
        self.t1        = t1
        self.t2        = None
        self.t3        = None
        self.t4        = None
        self.d_fw      = None
        self.d_bw      = None
        self.toffset   = None
        self.asymmetry = None

    def log_header(self):
        """Print logging header"""

        header = '{:>4} {:^23} {:^23} {:^23} {:^23} {:^9} {:^9}'.format(
            "idx", "t1", "t2", "t3", "t4", "delay_est", "x_est"
        )

        logger = logging.getLogger("DelayReqResp")
        logger.info(header)

    def set_t2(self, seq_num, t2):
        """Set Sync arrival timestamp

        Args:
            seq_num : Sequence number
            t2      : Sync arrival timestamp
        """
        assert(self.seq_num == seq_num)
        self.t2      = t2

    def set_t3(self, seq_num, t3):
        """Set Delay_Req departure timestamp

        Args:
            seq_num : Sequence number
            t3      : Delay_Req departure timestamp
        """
        assert(self.seq_num == seq_num)
        self.t3      = t3

    def set_t4(self, seq_num, t4):
        """Set Delay_Req departure timestamp

        Args:
            seq_num : Sequence number
            t4      : Delay_Req departure timestamp
        """
        assert(self.seq_num == seq_num)
        self.t4      = t4

    def set_forward_delay(self, seq_num, delay):
        """Save the "true" master-to-slave one-way delay

        This truth comes from the difference of RTC timestamps. Hence, although
        close, it still suffers from uncertainties and quantization.

        Args:
            seq_num : Sequence number
            delay   : Master-to-slave delay

        """
        assert(self.seq_num == seq_num)
        self.d_fw = delay

    def set_backward_delay(self, seq_num, delay):
        """Save the "true" slave-to-master one-way delay

        This truth comes from the difference of RTC timestamps.

        Args:
            seq_num : Sequence number
            delay   : Slave-to-master delay

        """
        assert(self.seq_num == seq_num)
        self.d_bw = delay

    def _estimate_delay(self):
        """Estimate the one-way delay

        Returns:
            The delay estimation in ns as a float
        """
        delay_est_ns = (float(self.t4 - self.t1) - float(self.t3 - self.t2)) / 2
        return delay_est_ns

    def _estimate_time_offset(self):
        """Estimate the time offset from master

        Returns:
            The time offset as a Timestamp object
        """
        offset_from_master = ((self.t2 - self.t1) - (self.t4 - self.t3)) / 2
        return offset_from_master

    def set_truth(self, master_tstamp, slave_tstamp):
        """Save the true time offset and asymmetry within the dataset

        Use also the supplied RTC timestamps to assess the true time offset at
        this point and evaluate the estimation.

        Args:
            master_tstamp : Timestamp from the master RTC
            slave_tstamp  : Timestamp from the slave RTC

        """

        self.toffset   = slave_tstamp - master_tstamp
        self.asymmetry = (self.d_fw - self.d_bw) / 2

        logger = logging.getLogger("DelayReqResp")
        logger.debug("m-to-s delay: %f\ts-to-m delay: %f\tasymmetry: %f" %(
            self.d_fw, self.d_bw, self.asymmetry))

    def process(self):
        """Process all four timestamps

        Wrap-up the delay request-response exchange by computing the associated
        metrics with the four collected timestamps.

        Returns:
            Dictionary with resulting metrics

        """

        # Estimations
        delay_est     = self._estimate_delay()
        toffset_est   = self._estimate_time_offset()

        # Save all relevant metrics on a dictionary
        results = {
            "idx"       : self.seq_num,
            "t1"        : self.t1,
            "t2"        : self.t2,
            "t3"        : self.t3,
            "t4"        : self.t4,
            "d"         : self.d_fw, # Sync one-way delay
            "d_est"     : delay_est,
            "x_est"     : float(toffset_est),
        }

        logger = logging.getLogger("DelayReqResp")

        # Append optionally-defined metrics
        if (self.asymmetry is not None):
            results["asym"] = self.asymmetry

        if (self.toffset is not None):
            # Time offset estimation error
            toffset_err = float(toffset_est - self.toffset)
            # Save on results
            results["x"]         = float(self.toffset)
            results["x_est_err"] = toffset_err

            logger.debug("time offset: %s\testimated: %s\terr: %s" %(
                self.toffset, toffset_est, toffset_err))

        line = '{:>4d} {:^23} {:^23} {:^23} {:^23} {:^9.1f} {:^9.1f}'.format(
            self.seq_num, str(self.t1), str(self.t2), str(self.t3),
            str(self.t4), delay_est, float(toffset_est)
        )
        logger.info(line)

        return results
