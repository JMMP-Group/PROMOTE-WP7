#!/bin/bash
#SBATCH --job-name=virtualise_eORCA025_SPNA20
#SBATCH --time=10:00:00
#SBATCH --mem=100G
#SBATCH --account=noc_msm
#SBATCH --partition=standard
#SBATCH --qos=standard

# ==============================================================
# run_virtualise_eORCA025_SPNA20_to_icechunk.slurm
#
# Description: SLURM script to virtualise the eORCA025 SPNA20
# model dataset to a local Icechunk repository.
#
# Created By: Ollie Tooth (oliver.tooth@noc.ac.uk)
# Created On: 2026-09-16
#
# ==============================================================
set -euo pipefail

# -- Python Environment -- #
# Activate Python virtual environment:
module unload jaspy
source ~/miniforge3/bin/activate
conda activate env_nemo

# -- Virtualise eORCA025 SPNA20 dataset to local Icechunk repository -- #
python3 virtualise_eORCA025_SPNA20_to_icechunk.py