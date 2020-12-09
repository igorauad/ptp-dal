# PTP Dataset Analysis Library (PTP-DAL)

This repository contains a Python package and associated scripts to analyze
synchronization via the IEEE 1588 precision time protocol (PTP). It analyzes
synchronization algorithms based on datasets containing PTP packet timestamps.

The PTP-DAL library implements several algorithms, such as packet selection,
least squares, and Kalman filtering. These are applied independently to the
timestamps provided on a given dataset. After processing the selected
algorithms, PTP-DAL outputs a comprehensive set of results comparing the
synchronization performance achieved by each algorithm and indicating several
aspects of the PTP network and environment, such as the packet delay variation
(PDV), PTP delay distributions, and temperature variations.

The project was developed to analyze datasets of timestamps generated by the
FPGA-based PTP synchronization testbed developed by [LASSE - 5G & IoT Research
Group](https://www.lasse.ufpa.br/), which has been used and explained in
publications such as the following:

- ["An FPGA-based Design of a Packetized Fronthaul Testbed with IEEE 1588 Clock
  Synchronization," European Wireless
  2017.](https://ieeexplore.ieee.org/document/8011327)
- ["Testbed Evaluation of Distributed Radio Timing Alignment Over Ethernet
  Fronthaul Networks," in IEEE
  Access.](https://ieeexplore.ieee.org/document/9088987)

Each dataset contains a number of PTP two-way exchanges. For each exchange, the
dataset includes the four timestamps involved in the two-way exchange (i.e., t1,
t2, t3, and t4). Furthermore, it includes auxiliary timestamps used to indicate
the true one-way delay of each PTP packet and the true time offset affecting the
slave on each exchange. This auxiliary information is used to analyze the error
between each time offset estimator and the actual time offset experienced by the
slave clock at any point in time.

The datasets produced by the testbed can be made available on demand. If you are
interested in exploring PTP-DAL using datasets acquired from LASSE's PTP
synchronization testbed, please read the [dataset access](#dataset-access)
section and get in touch with us directly through
[email](mailto:ptp.dal@gmail.com). Otherwise, this repository contains a
simulator capable of generating compatible datasets through
[simulation](#simulator).

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [PTP Dataset Analysis Library (PTP-DAL)](#ptp-dataset-analysis-library-ptp-dal)
    - [Python Environment](#python-environment)
    - [Scripts](#scripts)
        - [Main scripts:](#main-scripts)
        - [Complementary scripts:](#complementary-scripts)
    - [Analysis](#analysis)
    - [Analysis Recipes](#analysis-recipes)
    - [Dataset Cataloging](#dataset-cataloging)
    - [Simulator](#simulator)
    - [Dataset Access](#dataset-access)
        - [API Endpoints](#api-endpoints)
    - [Contact Us](#contact-us)

<!-- markdown-toc end -->


## Python Environment

The project requires Python 3.6 or higher.

If using *virtualenvwrapper*, run the following to create a virtual environment:

```
mkvirtualenv -r requirements.txt ptp
```

## Scripts

### Main scripts:

* `analyze.py` : Analyzes a dataset and compares synchronization algorithms.
* `batch.py` : Runs a batch of analyses (see the batch processing
  [recipes](recipes/)).
* `catalog.py` : Catalogs datasets acquired with the testbed.
* `dataset.py` : Downloads and searches datasets by communicating with the
  dataset database.

### Complementary scripts:

* `capture.py` : Acquires timestamp data from the testbed in real-time. This
  script is for internal use only. It requires the actual testbed
  infrastructure, which is not available in this repository.
* `compress.py` : Compresses a given dataset captured with the testbed.
* `ptp_plots.py`: Demonstrates a few plots that can be generated using the
  `ptp.metrics` module.
* `ptp_estimators.py`: Demonstrates estimators that can be used to post-process
   PTP measurements.
* `simulate.py` : Simulates PTP clocks and generates a timestamp dataset that
  can be processed with the same scripts used to process a testbed-generated
  dataset.
* `window_optimizer_demo.py` : Evaluates the performance of window-based
  estimators according to the observation window length.
* `kalman_demo.py`: Demonstrates the evaluation of Kalman filtering.

## Analysis

The main script for synchronization analysis is `analyze.py`, which can be
executed as follows:

```
./analyze.py -vvvv -f [dataset-filename]
```

The script will download the specified dataset automatically and process
it. Upon completion, the results become available in the `results/` directory.

## Analysis Recipes

Directory `recipes` contains preset recipes for running a batch of analyses
based on distinct datasets. Refer to the instructions [in the referred
directory](recipes/README.md).

## Dataset Cataloging

Every dataset downloaded through `analyze.py` gets cataloged automatically. The
cataloging produces a JSON file at `data/catalog.json` and an HTML version at
`data/index.html`.

The dataset catalog can also be generated manually by calling:

```
./catalog.py
```

## Simulator

PTP-DAL also offers a simulator to generate a timestamp dataset formatted
similarly to the datasets acquired from the testbed. With that, the same
algorithms that can process timestamps from testbed datasets can process the
data from simulated datasets.

To generate a simulation dataset, define the target number of PTP exchanges, and
run with argument `--save`. For example, for 10000 exchanges, run:

```
./simulate.py -vvvv -N 10000 --save
```

where argument `-vvvv` sets verbosity level 4 (info). Feel free to adjust the
verbosity level as needed. For example, level 5 (`-vvvvv`) prints a great amount
of debugging information.

After the simulation, the resulting (simulated) dataset is placed in the `data/`
directory, where the analysis script expects it.

> NOTE: all datasets generated by simulation are prefixed `sim-`. In contrast,
> datasets acquired serially from the testbed are prefixed with `serial-`.


## Dataset Access

The datasets acquired with the FPGA-based testbed are kept within the PTP
dataset database (DB). These are accessible through our PTP dataset API hosted
at <https://ptp.database.lasseufpa.org/api/>.

This API uses mutual SSL authentication, on which both client and server
authenticate each other through digital certificates. Hence, to use this
service, you need to obtain a valid client certificate signed by our
certification authority (CA).

If you are interested in accessing our datasets, please follow the procedure
below:

1. Generate a private/public key pair.

```bash
# Client key
openssl genrsa -out <your_name>.key 4096
```

2. Generate a certificate signing request (CSR), which contains your public
   key and is signed using your private key.

```bash
# CSR to obtain certificate
openssl req -new -key <your_name>.key -out <your_name>.csr
```

3. Send the CSR to us at [ptp.dal@gmail.com](mailto:ptp.dal@gmail.com) and let
   us know the network scenarios or types of datasets you are interested in
   exploring.

4. We sign your CSR and send you the final (CA-signed) digital certificate that
   you will use to access the dataset DB API.

5. Try accessing the dataset API:

First, run:
```
./dataset.py search
```

The application will prompt you for access information. When asked about
`Download via API or SSH?`, reply with `API` (or just press enter to accept the
default response). Next, fill in the paths to your private key (generated in
step 1) and the digital certificate (obtained in step 4).

After that, the command should return the list of datasets.

### API Endpoints

**Dataset download:**
GET: `https://ptp.database.lasseufpa.org/api/dataset/<dataset_name>`

**Dataset search**
POST: `https://ptp.database.lasseufpa.org/api/search`

## Contact Us

Contact information:

:email: [ptp.dal@gmail.com](mailto:ptp.dal@gmail.com)
