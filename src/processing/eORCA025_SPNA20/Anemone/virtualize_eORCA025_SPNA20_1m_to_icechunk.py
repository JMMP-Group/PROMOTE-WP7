"""
virtualize_eORCA025_SPNA20_to_icechunk.py

Description:
Script to virtualize eORCA025_SPNA20 JRA55-do NEMO output NetCDF files to
a virtual NEMODataTree in a local Icechunk repository.

Contact:
Ollie Tooth (oliver.tooth@noc.ac.uk)
"""
# === Import Dependencies === #
import logging

import icechunk
from nemo_cookbook import NEMODataTree
from OceanDataStore.cli import initialise_logging

logger = logging.getLogger(__name__)

# === Main Function === #
def main(store_fpath: str,
         years: str,
         iperio: bool,
         nftype: str,
         repo_fpath: str,
         update: bool,
         commit_years: str,
         commit_message: str
         ) -> None:
    """
    Virtualise NEMO AGRIF NetCDF output files to a local Icechunk repository.

    Parameters
    ----------
    store_fpath : str
        Path to the local directory containing the NEMO AGRIF netCDF output files.
    years : str
        Years of the NEMO AGRIF netCDF output files to virtualise (e.g. "1976", "19??", "????" etc.).
    iperio : bool
        Whether the NEMO model domain is zonally periodic (True) or not (False).
    nftype : str
        Type of north folding of NEMO model grid (e.g. "T", "F").
    repo_fpath : str
        Path to the local Icechunk repository where the virtual dataset will be stored.
    update : bool
        Whether to update the existing local Icechunk repository (True) or not (False).
    commit_years : str
        Year range to include in the commit message (e.g., "1976-01 - 1976-12").
    commit_message : str
        Commit message to use when saving the virtual dataset to the Icechunk repository.
    """
    # === Initialize logging === #
    initialise_logging()

    logger.info(f"======= NEMODataTree Virtualisation for Year -> {years} =======")

    # Define paths dictionary for nested NEMODataTree:
    paths = {
        "parent": {
            "domain": f"{store_fpath}/domain_cfg_mesh_mask.nc",
            "gridT": f"{store_fpath}/eORCA025_SPNA20_1m_grid_T_{years}*.nc",
            "gridU": f"{store_fpath}/eORCA025_SPNA20_1m_grid_U_{years}*.nc",
            "gridV": f"{store_fpath}/eORCA025_SPNA20_1m_grid_V_{years}*.nc",
            "gridW": f"{store_fpath}/eORCA025_SPNA20_1m_grid_W_{years}*.nc",
            },
        "child": {
            "1":{
                "domain": f"{store_fpath}/1_domain_cfg_mesh_mask.nc",
                "gridT": f"{store_fpath}/1_eORCA025_SPNA20_1m_grid_T_{years}*.nc",
                "gridU": f"{store_fpath}/1_eORCA025_SPNA20_1m_grid_U_{years}*.nc",
                "gridV": f"{store_fpath}/1_eORCA025_SPNA20_1m_grid_V_{years}*.nc",
                "gridW": f"{store_fpath}/1_eORCA025_SPNA20_1m_grid_W_{years}*.nc",
            }},
    }

    # Define nests dictionary for NEMODataTree:
    nests = {
        "1": {
        "parent": "/",
        "rx": 5,
        "ry": 5,
        "imin": 905,
        "imax": 1165,
        "jmin": 908,
        "jmax": 1155,
        "iperio": False
        }}

    # Define variables to drop from NEMODataTree:
    drop_vars = ["axis_nbounds"]

    # Define loadable variables for NEMODataTree:
    loadable_vars = ["time_counter", "nav_lon", "nav_lat", "deptht", "depthu", "depthv", "depthw"]

    # Create virtual NEMODataTree from paths:
    nemo = NEMODataTree.virtualize_from_paths(prefix=store_fpath,
                                                       paths=paths,
                                                       nests=nests,
                                                       drop_vars=drop_vars,
                                                       loadable_vars=loadable_vars,
                                                       name="eORCA025 SPNA20 JRA55-do",
                                                       iperio=iperio,
                                                       nftype=nftype,
                                                       nbghost_child=None
                                                      )

    # Rename 'thkcello' dimension to 'e3t' for T-grid datasets:
    nemo["gridT"].dataset = nemo["gridT"].dataset.rename({"thkcello": "e3t"})
    nemo["gridT/1_gridT"].dataset = nemo["gridT/1_gridT"].dataset.rename({"thkcello": "e3t"})

    logger.info("Completed: Created NEMODataTree from virtual datasets")

    # == Get Local Icechunk Repository == #
    # Define default Icechunk repository configuration:
    config = icechunk.RepositoryConfig.default()

    # Create new virtual container --> where our NEMO NetCDF outputs are located on the local filesystem:
    config.set_virtual_chunk_container(icechunk.VirtualChunkContainer(f"file://{store_fpath}/", icechunk.local_filesystem_store(repo_fpath)))

    # Define access credentials for accessing the virtual chunk container --> None for local filesystem:
    credentials = icechunk.credentials.containers_credentials({f"file://{store_fpath}/": icechunk.credentials.LocalFileSystemAccess})

    if update:
        # Open the existing local Icechunk repository:
        repo = icechunk.Repository.open(
                storage=icechunk.local_filesystem_storage(repo_fpath),
                config=config,
                authorize_virtual_chunk_access=credentials
            )
        logger.info(f"Completed: Opened existing local Icechunk repository -> {repo_fpath}")
    else:
        # Create new local Icechunk repository:
        repo = icechunk.Repository.create(
            storage=icechunk.local_filesystem_storage(repo_fpath),
            config=config,
            authorize_virtual_chunk_access=credentials
        )
        logger.info(f"Completed: Created new local Icechunk repository -> {repo_fpath}")

    # == Write NEMO T/U/V/W/F-grid virtual dataset to Icechunk repository == #
    grid_list = [
        'gridT',
        'gridU',
        'gridV',
        'gridW',
        'gridF',
        'gridT/1_gridT',
        'gridU/1_gridU',
        'gridV/1_gridV',
        'gridW/1_gridW',
        'gridF/1_gridF'
        ]

    for grid in grid_list:
        session = repo.writable_session("main")
        if update:
            nemo[grid].to_dataset().vz.to_icechunk(session.store, group=grid, append_dim="time_counter")
        else:
            nemo[grid].to_dataset().vz.to_icechunk(session.store, group=grid)
        snapshot_id = session.commit(f"{commit_message} -> {grid}")

        if grid == 'gridT':
            repo.save_config()
        
        logger.info(f"Completed: Saved NEMO model {grid} virtual dataset to Icechunk repository with snapshot ID -> {snapshot_id}")

    logger.info(f"Completed: Virtualised {commit_years} NEMO model dataset to Icechunk repository -> {repo_fpath}")


if __name__ == "__main__":
    # ================= INPUTS ================= #
    # File path to `store` directory in which all NEMO AGRIF NetCDF output files are included:
    store_fpath = "/dssgfs01/working/otooth/PROMOTE/eORCA025_SPNA20"

    # Zonal periodicity:
    iperio = True
    # North folding type
    nftype = "T"

    # File path to local Icechunk repository:
    repo_fpath = "/dssgfs01/working/otooth/PROMOTE/repos/eORCA025_SPNA20_1m"

    for yr in range(1958, 2024):
        # Update existing or create new Icechunk repository:
        if yr > 1958:
            update = True
        else:
            update = False

        # Define year expression (e.g., glob.glob(year_expr))
        year_expr = f"{yr}"
        # Define commit year expression for commit message:
        commit_year_expr = f"{yr}-01 - {yr}-12"

        # Define commit message for current year range:
        commit_msg = f"Virtualize eORCA025 SPNA20 JRA55-do monthly-mean NEMODataTree ({commit_year_expr})"

        # =========== VIRTUALISATION =========== #
        # Run virtualisation for current year range:
        main(store_fpath=store_fpath,
             years=year_expr,
             iperio=iperio,
             nftype=nftype,
             repo_fpath=repo_fpath,
             update=update,
             commit_years=commit_year_expr,
             commit_message=commit_msg
            )
