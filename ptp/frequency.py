"""Estimators
"""
import numpy as np
import logging, os, json
import ptp.cache
logger = logging.getLogger(__name__)


class Estimator():
    """Frequency offset estimator"""
    def __init__(self, data, delta=1):
        """Initialize the frequency offset estimator

        Args:
            data  : Array of objects with simulation data
            delta : (int > 0) Observation interval in samples. When set to 1,
                    estimates the frequency offsets based on consecutive data
                    entries.  When set to 2, estimates frequency offset i based
                    on timestamps from the i-th iteration and from iteration
                    'i-2', and so on.

        """
        assert(delta > 0)
        assert(isinstance(delta, int))
        self.data  = data
        self.delta = delta

    def _eval_drift_err(self, loss, criterion, n_samples=0, N=8192):
        """Evaluate the drift estimation error relative to true drift

        Assess the quality of the drift estimates by comparing them to the true
        time offset drifts. Do so considering that the true time offset drifts
        contain an uncertainty. Assuming that each true time offset is actually
        "x + u", where "u" is the label uncertainty, consider a maximum
        uncertainty on true drifts of "2u".

        Often the true drift between consecutive samples is significantly lower
        than the uncertainty "2u". Hence, it is often undesirable to consider
        the instantaneous drift estimation error, as it will be masked by the
        uncertainty. To overcome this problem, accumulate drift estimates and
        compare the cumulative values. Accumulate a window of drift estimates
        long enough such that the cumulative values exceeds the uncertainty
        significantly. For example, if a frequency offset as low as 10 ppb is
        expected, and "2*u = 16" ns, accumulate at least 16 seconds so that the
        cumulative drift values become 10x higher than the uncertainty.

        Another important requirement is that the drift estimates must be
        smooth. They are ultimately used for drift compensation within packet
        selection algorithms. On these algorithms, the drift is first
        subtracted, then re-added in the end. This means that the accuracy of
        the cumulative drifts relative to the true cumulative drift since the
        beginning of the dataset is not important. What matters the most is the
        accuracy of drift estimates within the observation window. Try to
        optimize the drifts such that they do not deviate too much from the true
        drifts over short-term windows.

        This function uses the drift estimates and true time offset values that
        are available internally on self.data.

        Args:
            loss      : Loss function (mse or max-error)
            criterion : Error criterion used for tuning: cumulative time offset
                        drift error or instantaneous time offset drift error.
            n_samples : Number of drift samples to consider (0, the default,
                        considers all samples)
            N         : Number of drift estimates to accumulate in a window.

        Returns:
            Scalar value representing the MSE (mean square error) or max|error|
            (maximum absolute error) of the current drift estimates.

        """
        assert(criterion in ['cumulative', 'instantaneous'])
        assert(loss in ["mse", "max-error"])

        # Instantaneous true and estimated drifts
        true_drift = np.array([(r["x"] - self.data[i-1]["x"])
                               for i,r in enumerate(self.data)
                               if "drift" in r])
        drift_est  = np.array([r["drift"] for r in self.data
                               if "drift" in r])

        if (criterion == 'instantaneous'):
            drift_err  = (drift_est - true_drift)[-n_samples:]
            if (loss == "mse"):
                return np.square(drift_err).mean()
            elif (loss == "max-error"):
                return np.amax(np.abs(drift_err))

        # Running-sum of drifts over a rolling window of N samples. If there is
        # less than N samples in the dataset, use a cumulative sum.
        if (len(self.data) <= N):
            true_cum_drift = true_drift.cumsum()
            cum_drift_est  = drift_est.cumsum()
        else:
            h              = np.ones(N)
            true_cum_drift = np.convolve(true_drift, h, mode="valid")
            cum_drift_est  = np.convolve(drift_est, h, mode="valid")

        # Normalized cumulative drift estimation errors
        #
        # Normalize by the absolute of the true drifts such that different
        # frequency offsets (with varying levels of drifts) are equally
        # weighted. For example, with 128 sample per second, a 10 ppb offset
        # leads to drifts in the order of 10 ns when accumulated over N=128,
        # whereas a 100 ppb freq. offset yields cumulative drifts in the order
        # of 100 ns. If we estimate cumulative drifts of 9 ns and 90 ns,
        # respectively, the absolute errors are 1 ns and 10 ns, respectively,
        # which are unfair to compare (e.g., the max-error loss will focus on
        # high frequency offsets). In contrast, the normalized errors are 0.1 in
        # both cases, which can be compared fairly.
        cum_drift_err = (cum_drift_est - true_cum_drift)[-n_samples:] \
                        / np.abs(true_cum_drift[-n_samples:])

        if (loss == "mse"):
            return np.square(cum_drift_err).mean()
        elif (loss == "max-error"):
            return np.amax(np.abs(cum_drift_err))

    def process(self, strategy="two-way"):
        """Process the data

        Estimate the frequency offset relative to the reference over all the
        data. Do so by comparing interval measurements of the slave and the
        master. This is equivalent to differentiating the time offset
        measurements.

        Args:
            strategy : Select between one-way, one-way-reversed, and two-way.
                       The one-way strategy uses the m-to-s timestamps (t1 and
                       t2) only. The two-way strategy relies on the two-way time
                       offset measurements (x_est), namely on all timestamps
                       (t1, t2, t3, and t4). The reversed one-way strategy
                       uses the s-to-m timestamps (t3 and t4) only.

        """
        assert(strategy in ["one-way", "one-way-reversed", "two-way"])
        logger.info("Processing with N=%d" %(self.delta))

        # Remove previous estimates in case they already exist
        for r in self.data:
            r.pop("y_est", None)

        if (strategy == "one-way"):
            t1           = np.array([float(r["t1"]) for r in self.data])
            t2           = np.array([float(r["t2"]) for r in self.data])
            delta_slave  = t2[self.delta:] - t2[:-self.delta]
            delta_master = t1[self.delta:] - t1[:-self.delta]
            y_est        = (delta_slave - delta_master) / delta_master
        elif (strategy == "one-way-reversed"):
            t3           = np.array([float(r["t3"]) for r in self.data])
            t4           = np.array([float(r["t4"]) for r in self.data])
            delta_slave  = t3[self.delta:] - t3[:-self.delta]
            delta_master = t4[self.delta:] - t4[:-self.delta]
            y_est        = (delta_slave - delta_master) / delta_master
        elif (strategy == "two-way"):
            t1           = np.array([float(r["t1"]) for r in self.data])
            x_est        = np.array([float(r["x_est"]) for r in self.data])
            delta_x      = x_est[self.delta:] - x_est[:-self.delta]
            delta_master = t1[self.delta:] - t1[:-self.delta]
            y_est        = delta_x / delta_master

        for i,r in enumerate(self.data[self.delta:]):
            r["y_est"] = y_est[i]

    def optimize_to_y(self, loss="mse", max_window_span=0.2):
        """Optimize the observation interval used for freq. offset estimation

        Optimizes the observation interval used for unbiased frequency offset
        estimations in order to minimize the error between the estimates and the
        true frequency offset. This minimization can be either in terms of the
        mean square error (MSE) or the maximum absolute error (max|error|).

        The problem with this approach is that the truth in "y" (the true
        frequency offset) is questionable. Since the true y values are also
        computed based on windows, the window length used for the truth
        computation affects results and may render the optimization below less
        effective for drift compensation.

        Args :
            loss            : Loss function used to optimize the window length
                              (mse or max-error),
            max_window_span : Maximum fraction of the dataset to be occupied by
                              the observation window. This parameter controls
                              the maximum tolerable latency to obtain the first
                              frequency offset estimate (by the end of the first
                              observation window).

        """
        assert(loss in ["mse", "max-error"])

        log_min_window = 1
        log_max_window = int(np.floor(np.log2(max_window_span*len(self.data))))
        log_window_len = np.arange(log_min_window, log_max_window + 1, 1)
        window_len     = 2**log_window_len
        max_window_len = window_len[-1]
        n_samples      = len(self.data) - max_window_len
        assert(n_samples > 0)
        # NOTE: n_samples is a number of samples that is guaranteed to be
        # available for all window lengths to be evaluated

        logger.info("Optimize observation window" %())
        logger.info("Try from N = %d to N = %d" %(
            2**log_min_window, 2**log_max_window))

        min_error = np.inf
        N_opt     = 0

        for N in window_len:
            for r in self.data:
                r.pop("y_est", None)

            self.delta = N
            self.process()

            y_err = np.array([ 1e9*(r["y_est"] - r["rtc_y"])
                               for r in self.data[self.delta:]
                               if ("y_est" in r and "rtc_y" in r) ])

            if (loss == "mse"):
                error = np.square(y_err[:n_samples]).mean()
                # Only use `n_samples` out of y_err. This way, all window
                # lengths are compared based on the same number of samples.
            elif (loss == "max-error"):
                error = np.amax(np.abs(y_err[:n_samples]))

            if (error < min_error):
                N_opt     = N
                min_error = error

        loss_label = "MSE" if loss == "mse" else "Max|Error|"
        logger.info("Minimum {}: {} ppb".format(loss_label, error))
        logger.info("Optimum N: {}".format(N_opt))
        self.delta = N_opt

    def optimize_to_drift(self, loss="mse", criterion='cumulative',
                          max_window_span=0.2):
        """Optimize the observation interval used for freq. offset estimation

        Optimize based on the time offset drift estimation errors. This
        optimizer can lead to better performance because, in the end, what we
        really care about is predicting drifts accurately.

        Args:
            loss            : Loss function used to optimize the window length
                              (mse or max-error).
            criterion       : Whether the loss function is applied to the
                              cumulative time offset drift or the instantaneous
                              time offset drift error.
            max_window_span : Maximum fraction of the dataset to be occupied by
                              the observation window. This parameter controls
                              the maximum tolerable latency to obtain the first
                              frequency offset and time offset drift estimates
                              (by the end of the first observation window).

        Note:
            The cumulative criterion typically leads to better optimization
            performance. The absolute criterion considers estimation errors that
            are often masked by the uncertainty on dataset labels. For example,
            if the truth labels have an uncertainty of +-8 ns and the
            instantaneos drift error is < 1 ns, then the instataneous drift
            error becomes negligible relative to the uncertainty. In contrast,
            the cumulative criterion accumulates error such that the cumulative
            values are significantly greater than the intrinsic uncertainty on
            dataset labels. For example, if the instantaneous drift is in the
            order of 1 ns and is accumulated over 200 samples, the cumulative
            result (around 200 ns) becomes significantly greater than the truth
            uncertainty (e.g., 8 ns). Consequently, the optimization based on
            cumulative error considers the actual drift estimation errors.

        """
        assert(criterion in ['cumulative', 'instantaneous'])
        assert(loss in ["mse", "max-error"])

        log_min_window = 1
        log_max_window = int(np.floor(np.log2(max_window_span*len(self.data))))
        log_window_len = np.arange(log_min_window, log_max_window + 1, 1)
        window_len     = 2**log_window_len
        max_window_len = window_len[-1]
        n_samples      = len(self.data) - max_window_len
        assert(n_samples > 0)
        # NOTE: n_samples is a number of samples that is guaranteed to be
        # available for all window lengths to be evaluated

        logger.info("Optimize observation window" %())
        logger.info("Try from N = %d to N = %d" %(
            2**log_min_window, 2**log_max_window))

        m_error     = np.inf
        N_opt       = 0
        for N in window_len:
            for r in self.data:
                r.pop("y_est", None)
                r.pop("drift", None)

            self.delta = N
            self.process()
            self.estimate_drift()

            error = self._eval_drift_err(loss, criterion, n_samples)

            if (error < m_error):
                m_error = error
                N_opt   = N

        loss_label = "MSE" if loss == "mse" else "Max|Error|"
        logger.info("Minimum {}: {} ppb".format(loss_label, m_error))
        logger.info("Optimum N: {}".format(N_opt))
        self.delta = N_opt

    def set_truth(self, delta=None):
        """Set "true" frequency offset based on "true" time offset measurements

        Args:
            delta : (int > 0) Observation interval in samples. When set to 1,
                    estimates the frequency offsets based on consecutive data
                    entries.  When set to 2, estimates frequency offset i based
                    on timestamps from the i-th iteration and from iteration
                    'i-2', and so on. When set to None, use the delta value
                    set in self.delta (default: None)
        """
        for r in self.data:
            r.pop("rtc_y", None)

        delta = delta or self.delta
        t1    = np.array([float(r["t1"]) for r in self.data])
        x     = np.array([r["x"] for r in self.data])
        dx    = x[delta:] - x[:-delta]
        dt1   = t1[delta:] - t1[:-delta]
        y     = dx / dt1

        for i,r in enumerate(self.data[delta:]):
            r["rtc_y"] = y[i]

    def estimate_drift(self):
        """Estimate the incremental drifts due to frequency offset

        On each iteration, the true time offset changes due to the instantaneous
        frequency offset. On iteration n, with freq. offset y[n], it will
        roughly change w.r.t. the previous iteration by:

        drift[n] = y[n] * (t1[n] - t1[n-1])

        Estimate these incremental changes and save on the dataset.

        """
        # Clean previous estimates
        for r in self.data:
            r.pop("drift", None)

        # Compute the drift within the observation window
        for i,r in enumerate(self.data[1:]):
            if ("y_est" in r):
                delta = float(r["t1"] - self.data[i]["t1"])
                # NOTE: index i is the enumerated index, not the data entry
                # index. Since we get self.data[1:] (i.e. starting from index
                # 1), "i" lags the actual data index by 1.
                r["drift"] = r["y_est"] * delta

    def loop(self, damping=1.0, loopbw=0.001, settling=0.2):
        """Estimate time offset drifts using PI loop

        The PI loop tries to minimize the error between the input time offset
        estimate and the time offset that is expected based on not only the
        previous estimate, but also the loop's notion of frequency offset. In
        the long term, the loop should converge to learning the average time
        offset drift (or frequency offset) such that the error is minimized.

        The time offset drift estimates that are produced by the loop are only
        saved in the main data list after the loop settles. Other blocks will
        use the presence of drift estimates to infer when drift estimates are
        locked. In other words, if the "drift" key is not in a dict of the data
        list, the loop is not locked yet at this point.

        Note that the convergence of the loop is not explicitly tested
        here. Instead, we simply define the portion of the dataset that can be
        used for settling. All estimates produced past this portion of the
        dataset are saved, the other values are discarded. The rationale is that
        the optimizer also considers the same settling time margin. Hence, if
        the damping and loopbw parameters came from the optimizer, the values
        past the chosen settling time are already optimal and very likely
        effectively settled (converged).

        Args:
            damping  : Damping factor
            loopbw   : Loop bandwidth
            settling : Fraction of the dataset over which the loop can settle.
                       Results are only saved after this portion of the dataset.

        """
        logger.debug("Run PI loop with damping {:f} and loop bw {:f}".format(
            damping, loopbw))

        # Compute the proportional and integral gains
        theta_n  = loopbw / (damping + (1.0/(4 * damping)))
        denomin  = (1 + 2*damping*theta_n + (theta_n**2))
        Kp_K0_K1 = (4 * damping * theta_n) / denomin
        Kp_K0_K2 = (4 * (theta_n**2)) / denomin
        # And since Kp and K0 are assumed unitary
        Kp       = Kp_K0_K1 # proportional gain
        Ki       = Kp_K0_K2 # integrator gain

        # Clean previous estimates
        for r in self.data:
            r.pop("drift", None)
            r.pop("x_loop", None)

        # Index after which the loop is assumed to be settled
        i_settling = int(np.floor(settling * len(self.data)))

        # Run loop
        f_int = 0
        dds   = self.data[0]["x_est"]

        for i, r in enumerate(self.data):
            x_est      = r["x_est"]
            err        = x_est - dds
            f_prop     = Kp * err
            f_int     += Ki * err
            f_err      = f_prop + f_int

            if (i >= i_settling):
                r["drift"]  = f_err
                r["x_loop"] = dds

            dds += f_err

    def _is_cfg_loop_valid(self, data, error):
        """Check if the cached PI loop configuration is valid.

        The configuration is assumed valid if 1) the number of samples contained
        in the cached data is the same as the number of samples currently within
        self.data; and 2) the error (absolute or cumulative) criterion used for
        tuning the parameters is also the same.

        Args:
            data  : Cached optimal loop configuration
            error : Error criterion used for tuning: cumulative or absolute

        """
        is_valid  = (data is not None) and \
                    (data['n_samples'] == len(self.data)) and \
                    (data['error'] == error)

        return is_valid

    def optimize_loop(self, criterion='cumulative', loss="mse", cache=None,
                      cache_id='loop', force=False, max_transient=0.2):
        """Find loop parameters that minimize the drift estimation error

        Tries some pre-defined damping factor and loop bandwidth values.

        By default the damping factor and loop bandwidth are tuned using the
        cumulative drift instead of the absolute. This is because the latter
        leads to a time offset drift estimation that is very close to the
        'optimize_to_y', while the former yield the best estimation performance.

        Args:
            criterion     : Error criterion used for tuning: cumulative or
                            instantaneous time offset drift error.
            loss          : Loss function (mse or max-error).
            cache         : Cache handler used to save the optimal configuration
                            on a JSON file.
            cache_id      : Cache object identifier
            force         : Force processing even if a configuration file with
                            the optimal parameters already exists in cache.
            max_transient : Maximum fraction of the dataset to be occupied by
                            the transient phase of the loop. This parameter
                            controls the maximum tolerable latency to obtain the
                            first drift estimates.

        """
        assert(criterion in ['cumulative', 'instantaneous'])
        assert(loss in ["mse", "max-error"])

        # Check if a cached configuration file exists and is valid
        if (cache is not None):
            assert(isinstance(cache, ptp.cache.Cache)), "Invalid cache object"
            cached_loop_cfg = cache.load(cache_id)

            if (cached_loop_cfg and not force):
                if (self._is_cfg_loop_valid(cached_loop_cfg, criterion)):
                    best_damping = cached_loop_cfg['damping']
                    best_loopbw  = cached_loop_cfg['loopbw']

                    return best_damping, best_loopbw
        else:
            logging.info("Unable to find cached configuration file")

        damping_vec  = [0.5, 0.707, 1.0, 1.2, 1.5, 1.8, 2.0]
        loopbw_vec   = np.concatenate((
            np.arange(0.1, 1.0, 0.1),
            np.arange(0.01, 0.1, 0.01),
            np.arange(0.001, 0.01, 0.001),
            np.arange(0.0001, 0.001, 0.0001),
            np.arange(0.00001, 0.0001, 0.00001)))
        m_error      = np.inf
        best_damping = None
        best_loopbw  = None

        for damping in damping_vec:
            for loopbw in loopbw_vec:
                # Run loop with the given configurations
                self.loop(damping = damping, loopbw = loopbw,
                          settling=max_transient)

                # Evaluate the drift estimation error
                error = self._eval_drift_err(loss, criterion)
                # NOTE: there is no need to restrict the range of samples to be
                # used in this error evaluation. The loop only saves the
                # estimates that are past the desired transient. Hence, all
                # samples considered within self._eval_drift_err() are already
                # within the desired portion of the dataset used for analysis.

                if (error < m_error):
                    m_error      = error
                    best_damping = damping
                    best_loopbw  = loopbw

        logger.info("PI loop optimization")
        logger.info("Damping factor: {:f}".format(best_damping))
        logger.info("Loop bandwidth: {:f}".format(best_loopbw))

        if (cache is not None):
            # Save optimal configuration
            cache.save({'n_samples' : len(self.data),
                        'error'     : criterion,
                        'damping'   : best_damping,
                        'loopbw'    : best_loopbw},
                       identifier=cache_id)

        return best_damping, best_loopbw

