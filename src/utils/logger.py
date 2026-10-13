import logging
import os

def setup_logging(job_run, log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    filename = f"{log_dir}/etl_{job_run:%Y-%m-%d_%H-%M-%S}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(filename, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return filename