#!/bin/bash
#SBATCH --job-name=virtualize_eORCA025_SPNA20
#SBATCH --time=05:00:00
#SBATCH --partition=compute
#SBATCH --ntasks=1
#SBATCH --mem=60G

# ==============================================================
# run_virtualize_eORCA025_SPNA20_to_icechunk.slurm
#
# Description: SLURM script to virtualise the eORCA025 SPNA20
# model dataset to a local Icechunk repository.
#
# Created By: Ollie Tooth (oliver.tooth@noc.ac.uk)
# Created On: 2026-11-19
#
# ==============================================================
set -euo pipefail

# -- Python Environment -- #
# Activate Python virtual environment:
source /dssgfs01/working/otooth/miniforge3/bin/activate
conda activate env_nemo

# -- Virtualise eORCA025 SPNA20 dataset to local Icechunk repository -- #
python3 virtualize_eORCA025_SPNA20_1m_to_icechunk.py
# python3 virtualize_eORCA025_SPNA20_1d_to_icechunk.py
