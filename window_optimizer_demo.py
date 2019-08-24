"""Analyse the estimators performance as a function of window length
"""
import argparse, logging, sys
import ptp.runner, ptp.reader, ptp.window, ptp.frequency
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import numpy as np
import time, re

def main():
    # Available estimators
    est_op = ptp.window.Optimizer.est_op
    est_choices = [k for k in est_op] + ['all']

    parser = argparse.ArgumentParser(description="Max|TE| vs window")
    parser.add_argument('-e', '--estimator',
                        default='all',
                        help='Window-based estimator',
                        choices=est_choices)
    parser.add_argument('-p', '--plot',
                        default=False,
                        action='store_true',
                        help='Whether or not to plot results')
    parser.add_argument('--save-plot',
                        default=False,
                        action='store_true',
                        help='Whether or not to save plot results')
    parser.add_argument('--global-plot',
                        default=False,
                        action='store_true',
                        help='Whether or not to plot global curve')
    parser.add_argument('--no-plot-info',
                        default=False,
                        action='store_true',
                        help='Whether or not to save window information in plot')
    parser.add_argument('-s', '--save',
                        default=False,
                        action='store_true',
                        help='Whether or not to save window configurations')
    exc_group = parser.add_mutually_exclusive_group()
    exc_group.add_argument('-f', '--file',
                        default=None,
                        help='Serial capture file.')
    exc_group.add_argument('-N', '--num-iter',
                        default=2000,
                        type=int,
                        help='Number of iterations if running simulation')
    parser.add_argument('--no-stop',
                        default=False,
                        action='store_true',
                        help='Do not apply early stopping')
    parser.add_argument('--force',
                        default=False,
                        action='store_true',
                        help='Force processing even if already done previously')
    parser.add_argument('--fine',
                        default=False,
                        action='store_true',
                        help='Whether to enable window optimizer fine pass')
    parser.add_argument('--verbose', '-v', action='count', default=1,
                        help="Verbosity (logging) level")
    args = parser.parse_args()

    logging_level = 70 - (10 * args.verbose) if args.verbose > 0 else 0
    logging.basicConfig(stream=sys.stderr, level=logging_level)

    if (args.file is None):
        # Run PTP simulation
        ptp_src  = ptp.runner.Runner(n_iter=args.num_iter)
        ptp_src.run()
        T_ns     = ptp_src.sync_period*1e9

    else:
        # Load the simulation data
        if (args.file.endswith('.npz')):
            ptp_src = ptp.runner.Runner()
            ptp_src.load(args.file)

        # Run reader process
        elif (args.file.endswith('.json')):
            ptp_src = ptp.reader.Reader(args.file)
            ptp_src.run()

        # Get sync period from metadata
        if (hasattr(ptp_src, 'metadata') and
            'sync_period' in ptp_src.metadata and
            ptp_src.metadata['sync_period'] is not None):
            T_ns = ptp_src.metadata['sync_period']*1e9
        else:
            # FIXME we should use at least a command-line variable
            T_ns = 1e9/4

    # Estimate frequency offset and corresponding drifts
    freq_delta = 64
    freq_estimator = ptp.frequency.Estimator(ptp_src.data, delta=freq_delta)
    freq_estimator.set_truth(delta=freq_delta)
    freq_estimator.optimize()
    freq_estimator.process()
    freq_estimator.estimate_drift()

    # Optimize window lengths (based on Max|TE|)
    window_optimizer = ptp.window.Optimizer(ptp_src.data, T_ns)
    window_optimizer.process(args.estimator, file=args.file, save=args.save,
                             plot=args.plot, early_stopping=(not args.no_stop),
                             save_plot=args.save_plot, force=args.force,
                             plot_info=(not args.no_plot_info),
                             global_plot=args.global_plot,
                             fine_pass=args.fine)

if __name__ == "__main__":
    main()
