import os
import sys
import argparse
import shlex
from pprint import pprint

import numpy as np

from sklearn.grid_search import ParameterGrid

from clusterlib.scheduler import queued_or_running_jobs
from clusterlib.scheduler import submit
from clusterlib.storage import sqlite3_loads

from main import WORKING_DIR
from main import make_hash
from main import parse_arguments
from main import get_sqlite3_path

LOG_DIRECTORY = os.path.join(WORKING_DIR, "logs")

ALL_FLUORESCENCE = [os.path.join(WORKING_DIR, "datasets", x)
                    for x in os.listdir(os.path.join(WORKING_DIR,
                                                     "datasets"))
                    if (x.startswith("fluorescence_"))]

ALL_NETWORKS = [os.path.basename(os.path.splitext(x)[0]).split("_", 1)[1]
                for x in ALL_FLUORESCENCE]


OUTPUT_DIR = os.path.join(WORKING_DIR, "submission")

NORMAL = [{
    "output_dir": [OUTPUT_DIR],
    "network": [network],
    "fluorescence": [fluorescence],
    "method": ["simple", "tuned"],
    "directivity": [0, 1],
} for fluorescence, network in zip(ALL_FLUORESCENCE, ALL_NETWORKS)]

HIDDEN_NEURON = [{
    "output_dir": [OUTPUT_DIR],
    "network": [network],
    "fluorescence": [fluorescence],
    "method": ["simple", "tuned"],
    "directivity": [0, 1],
    "killing": range(1, 11),
}
for fluorescence, network in zip(ALL_FLUORESCENCE, ALL_NETWORKS)
if network in ("normal-3", "normal-4")
]

PARAMETER_GRID = ParameterGrid(NORMAL + HIDDEN_NEURON)

TIME = dict()
MEMORY = dict()

def compute_scores(f_ground_truth, f_prediction):
    print("--")
    print(f_ground_truth)
    print(f_prediction)


if __name__ == "__main__":

    # Argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', default=False, action="store_true")
    parser.add_argument('-v', '--verbose', default=False, action="store_true")
    parser.add_argument('-s', '--scores', default=False, action="store_true",
                        help="compute scores")

    args = vars(parser.parse_args())


    # Create log direcotyr if needed
    if not os.path.exists(LOG_DIRECTORY):
        os.makedirs(LOG_DIRECTORY)

    # Get running jobs
    all_jobs_running = set(queued_or_running_jobs())
    all_jobs_done = sqlite3_loads(get_sqlite3_path())

    # Intialize some counter for reporting
    n_jobs_running = 0
    n_jobs_done = 0
    n_jobs_launched = 0

    # Launch if necessary experiments
    for parameters in PARAMETER_GRID:
        job_hash = make_hash(parameters)

        if job_hash in all_jobs_running:
            n_jobs_running +=1

        elif job_hash in all_jobs_done:
            n_jobs_done += 1

            if args["scorse"]:
                fname = os.path.join(OUTPUT_DIR, "%s.csv" % job_hash)
                ground_truth = os.path.join(WORKING_DIR, "datasets",
                                            "network_%s.txt"
                                            % parameters["network"])
                compute_scores(fname, ground_truth)



        else:
            n_jobs_launched += 1
            cmd_parameters = " ".join("--%s %s" % (key, parameters[key])
                                      for key in sorted(parameters))

            scripts_args = parse_arguments(shlex.split(cmd_parameters))
            if make_hash(scripts_args) != job_hash:
                pprint(scripts_args)
                pprint(parameters)
                raise ValueError("hash are not equal, all parameters are "
                                 "not specified.")

            cmd = submit(job_command="%s main.py %s"
                                     % (sys.executable, cmd_parameters),
                         job_name=job_hash,
                         time="100:00:00",
                         memory=24000,
                         log_directory=LOG_DIRECTORY,
                         backend="slurm")

            if not args["debug"]:
                os.system(cmd)
            elif args["verbose"]:
                print("[launched] %s" % job_hash)
                print(cmd)

                if os.path.exists(os.path.join(LOG_DIRECTORY,
                                               "%s.txt" % job_hash)):
                    os.system("cat %s" % os.path.join(LOG_DIRECTORY,
                                                      "%s.txt" % job_hash))

    print("\nSummary launched")
    print("------------------")
    print("n_jobs_runnings = %s" % n_jobs_running)
    print("n_jobs_done = %s" % n_jobs_done)
    print("n_jobs_launched = %s" % n_jobs_launched)
