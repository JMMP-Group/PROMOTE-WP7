"""
virtualise_eORCA025_SPNA20_to_icechunk.py

Description:
Script to virtualise eORCA025_SPNA20 NEMO output NetCDF files to
a virtual NEMODataTree in a local Icechunk repository.

Contact:
Ollie Tooth (oliver.tooth@noc.ac.uk)
"""
# === Import Dependencies === #
import glob
import logging
import warnings

import icechunk
import xarray as xr
from nemo_cookbook import NEMODataTree
from obspec_utils.registry import ObjectStoreRegistry
from obstore.store import LocalStore
from OceanDataStore.cli import initialise_logging
from virtualizarr import open_virtual_dataset, open_virtual_mfdataset
from virtualizarr.parsers import HDFParser

warnings.filterwarnings(
  "ignore",
  message="Numcodecs codecs are not in the Zarr version 3 specification*",
  category=UserWarning
)

logger = logging.getLogger(__name__)

# === Utility Functions === #
def create_virtual_dataset(
    filepaths: list[str],
    drop_vars: list[str] | None = None,
    loadable_variables: list[str] | None = None,
    decode_times: bool=True,
    parallel: str="dask",
    combine: str="by_coords",
    combine_attrs: str="drop_conflicts"
    ) -> xr.Dataset:
    # -- Prepare registry for virtual dataset -- #
    file_urls = [f"file://{fp}" for fp in filepaths]
    store = LocalStore(prefix=store_fpath)
    registry = ObjectStoreRegistry(stores={file_url : store for file_url in file_urls})

    # Define parser for virtual dataset:
    parser = HDFParser(drop_variables=drop_vars)

    # Open virtual dataset from filepaths:
    if len(filepaths) == 1:
        vds = open_virtual_dataset(
            url=filepaths[0],
            registry=registry,
            parser=parser,
            decode_times=decode_times
        )
    else:
        vds = open_virtual_mfdataset(
            urls=filepaths,
            registry=registry,
            parser=parser,
            loadable_variables=loadable_variables,
            decode_times=decode_times,
            parallel=parallel,
            combine=combine,
            combine_attrs=combine_attrs
        )

    return vds


def add_ancillary_attrs(
    ds: xr.Dataset,
    grid_type: str="T"
    ) -> xr.Dataset:
    """
    Add attributes to NEMO model grid ancillary variables.

    Parameters
    ----------
    ds : xr.Dataset
        Input xarray.Dataset.
    grid_type : str, optional
        Type of NEMO grid to add ancillary attributes.
        Default is "T".

    Returns
    -------
    xr.Dataset
        xarray.Dataset with added ancillary variable attributes.
    """
    ugrid_type = grid_type.upper()
    lgrid_type = grid_type.lower()

    # Rename thkcello -> e3t / e3u / e3v / e3w:
    if "thkcello" in ds:
        ds = ds.rename({"thkcello": f"e3{lgrid_type}"})

    # Longitude:
    if f"glam{lgrid_type}." in ds:
        ds[f"glam{lgrid_type}."].encoding.update({"dtype": "float32"})
        ds[f"glam{lgrid_type}."].attrs["standard_name"] = "longitude"
        ds[f"glam{lgrid_type}."].attrs["long_name"] = f"Longitude of Ocean {ugrid_type}-Grid Points"
        ds[f"glam{lgrid_type}."].attrs["units"] = "degree_east"
    # Latitude:
    if f"gphit{lgrid_type}." in ds:
        ds[f"gphit{lgrid_type}."].encoding.update({"dtype": "float32"})
        ds[f"gphit{lgrid_type}."].attrs["standard_name"] = "latitude"
        ds[f"gphit{lgrid_type}."].attrs["long_name"] = f"Latitude of Ocean {ugrid_type}-Grid Points"
        ds[f"gphit{lgrid_type}."].attrs["units"] = "degree_north"
    # Depth:
    if f"depth{lgrid_type}." in ds:
        ds[f"depth{lgrid_type}."].encoding.update({"dtype": "float32"})
        ds[f"depth{lgrid_type}."].attrs["standard_name"] = "depth"
        ds[f"depth{lgrid_type}."].attrs["long_name"] = f"Depth of Ocean {ugrid_type}-Grid Points"
        ds[f"depth{lgrid_type}."].attrs["positive"] = "down"
        ds[f"depth{lgrid_type}."].attrs["units"] = "m"
    # Land-Sea Masks:
    if f"{lgrid_type}mask" in ds:
        ds[f"{lgrid_type}mask"].attrs["standard_name"] = "land_sea_mask"
        ds[f"{lgrid_type}mask"].attrs["long_name"] = f"Ocean {ugrid_type}-Grid Land-Sea Mask"
    if f"{lgrid_type}maskutil" in ds:
        ds[f"{lgrid_type}maskutil"].attrs["standard_name"] = "land_sea_unique_point_mask"
        ds[f"{lgrid_type}maskutil"].attrs["long_name"] = f"Ocean {ugrid_type}-Grid Land-Sea Unique Point Mask"
    # Grid Scale Factors:
    if f"e1{lgrid_type}" in ds:
        ds[f"e1{lgrid_type}"].attrs["standard_name"] = "grid_scale_factor_in_x_direction"
        ds[f"e1{lgrid_type}"].attrs["long_name"] = f"Horizontal {ugrid_type}-Grid Scale Factor in X-Direction"
        ds[f"e1{lgrid_type}"].attrs["units"] = "m"
    if f"e2{lgrid_type}" in ds:
        ds[f"e2{lgrid_type}"].attrs["standard_name"] = "grid_scale_factor_in_y_direction"
        ds[f"e2{lgrid_type}"].attrs["long_name"] = f"Horizontal {ugrid_type}-Grid Scale Factor in Y-Direction"
        ds[f"e2{lgrid_type}"].attrs["units"] = "m"
    if f"e3{lgrid_type}" in ds:
        ds[f"e3{lgrid_type}"].attrs["standard_name"] = "grid_scale_factor_in_z_direction_at_surface"
        ds[f"e3{lgrid_type}"].attrs["long_name"] = f"Reference Vertical {ugrid_type}-Grid Scale Factor in Z-Direction"
        ds[f"e3{lgrid_type}"].attrs["units"] = "m"

    # Drop duplicate time variables:
    ds = ds.drop_vars(
                ["time_centered", "time_centered_bounds"],
                errors="ignore",
            )

    # Correct coordinates attribute:
    for var in ds.variables.values():
        if "coordinates" in var.attrs:
            var.attrs["coordinates"] = (
                var.attrs["coordinates"]
                .replace("time_centered", "time_counter")
            )

    return ds


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
    Virtualise NEMO AGRIF netCDF output files to a local Icechunk repository.

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

    # === NEMO domain_cfg === #
    # --> Parent
    filepath = f"{store_fpath}/domain_mesh_mask.nc"
    vds_domain_parent = create_virtual_dataset(filepaths=[filepath]).squeeze(drop=True)

    logger.info("Completed: Opened NEMO parent domain_cfg virtual dataset")

    # --> Child
    filepath = f"{store_fpath}/1_domain_mesh_mask.nc"
    vds_domain_child = create_virtual_dataset(filepaths=[filepath]).squeeze(drop=True)

    logger.info("Completed: Opened NEMO child domain_cfg virtual dataset")

    # === NEMO T-grid === #
    # --> Parent
    filepaths = sorted(glob.glob(f"{store_fpath}/nemo_dy838o_1m_{years}*_grid-T.nc"))
    vds_gridT_parent = create_virtual_dataset(
        filepaths=filepaths,
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'deptht'],
    )

    logger.info("Completed: Opened NEMO parent T-grid virtual dataset")

    # --> Child
    filepaths = sorted(glob.glob(f"{store_fpath}/nemo_1-dy838o_1m_{years}*_grid-T.nc"))
    vds_gridT_child = create_virtual_dataset(
        filepaths=filepaths,
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'deptht'],
    )

    logger.info("Completed: Opened NEMO child T-grid virtual dataset")

    # === NEMO icemod === #
    # --> Parent
    filepaths = sorted(glob.glob(f"{store_fpath}/si3_dy838i_1m_{years}*_icemod.nc"))
    vds_icemod_parent = create_virtual_dataset(
        filepaths=filepaths,
        drop_vars=["y", "x", "nvertex", "axis_nbounds"],
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'ncatice'],
    )

    logger.info("Completed: Opened NEMO parent icemod virtual dataset")

    # --> Child
    filepaths = sorted(glob.glob(f"{store_fpath}/si3_1-dy838i_1m_{years}*_icemod.nc"))
    vds_icemod_child = create_virtual_dataset(
        filepaths=filepaths,
        drop_vars=["y", "x", "nvertex", "axis_nbounds"],
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'ncatice'],
    )

    logger.info("Completed: Opened NEMO child icemod virtual dataset")

    # == Merge NEMO T-grid and icemod datasets == #
    # --> Parent
    vds_gridT_parent_merged = xr.combine_by_coords([vds_gridT_parent, vds_icemod_parent],
                                                   compat="override", # use gridT
                                                   combine_attrs="override" # use gridT
                                                   )
    
    logger.info("Completed: Merged NEMO parent T-grid and icemod virtual datasets")
    
    # --> Child
    vds_gridT_child_merged = xr.combine_by_coords([vds_gridT_child, vds_icemod_child],
                                                  compat="override", # use gridT
                                                  combine_attrs="override" # use gridT
                                                  )

    logger.info("Completed: Merged NEMO child T-grid and icemod virtual datasets")

    # === NEMO U-grid === #
    # --> Parent
    filepaths = sorted(glob.glob(f"{store_fpath}/nemo_dy838o_1m_{years}*_grid-U.nc"))
    vds_gridU_parent = create_virtual_dataset(
        filepaths=filepaths,
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'depthu'],
    )

    logger.info("Completed: Opened NEMO parent U-grid virtual dataset")

    # --> Child
    filepaths = sorted(glob.glob(f"{store_fpath}/nemo_1-dy838o_1m_{years}*_grid-U.nc"))
    vds_gridU_child = create_virtual_dataset(
        filepaths=filepaths,
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'depthu'],
    )

    logger.info("Completed: Opened NEMO child U-grid virtual dataset")

    # === NEMO V-grid === #
    # --> Parent
    filepaths = sorted(glob.glob(f"{store_fpath}/nemo_dy838o_1m_{years}*_grid-V.nc"))
    vds_gridV_parent = create_virtual_dataset(
        filepaths=filepaths,
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'depthv'],
    )

    logger.info("Completed: Opened NEMO parent V-grid virtual dataset")

    # --> Child
    filepaths = sorted(glob.glob(f"{store_fpath}/nemo_1-dy838o_1m_{years}*_grid-V.nc"))
    vds_gridV_child = create_virtual_dataset(
        filepaths=filepaths,
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'depthv'],
    )

    logger.info("Completed: Opened NEMO child V-grid virtual dataset")

    # === NEMO W-grid === #
    # --> Parent
    filepaths = sorted(glob.glob(f"{store_fpath}/nemo_dy838o_1m_{years}*_grid-W.nc"))
    vds_gridW_parent = create_virtual_dataset(
        filepaths=filepaths,
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'depthw'],
    )

    logger.info("Completed: Opened NEMO parent W-grid virtual dataset")

    # --> Child
    filepaths = sorted(glob.glob(f"{store_fpath}/nemo_1-dy838o_1m_{years}*_grid-W.nc"))
    vds_gridW_child = create_virtual_dataset(
        filepaths=filepaths,
        loadable_variables=['time_counter', 'nav_lon', 'nav_lat', 'depthw'],
    )

    logger.info("Completed: Opened NEMO child W-grid virtual dataset")

    # === Create NEMODataTree from virtual datasets === #
    # Define datasets dictionary for virtual NEMODataTree:
    datasets = {"parent": {"domain": vds_domain_parent,
                           "gridT": add_ancillary_attrs(vds_gridT_parent_merged, "T"),
                           "gridU": add_ancillary_attrs(vds_gridU_parent, "U"),
                           "gridV": add_ancillary_attrs(vds_gridV_parent, "V"),
                           "gridW": add_ancillary_attrs(vds_gridW_parent, "W"),
                           },
                "child": {
                    "1":{"domain": vds_domain_child,
                         "gridT": add_ancillary_attrs(vds_gridT_child_merged, "T"),
                         "gridU": add_ancillary_attrs(vds_gridU_child, "U"),
                         "gridV": add_ancillary_attrs(vds_gridV_child, "V"),
                         "gridW": add_ancillary_attrs(vds_gridW_child, "W"),
                         }},
                }
    
    # Define nests dictionary for virtual NEMODataTree:
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
    
    # Create virtual NEMODataTree:
    nemo = NEMODataTree.from_datasets(datasets=datasets,
                                      nests=nests,
                                      iperio=iperio,
                                      nftype=nftype,
                                      read_mask=True,
                                      nbghost_child=None
                                      )

    logger.info("Completed: Created NEMODataTree from virtual datasets")

    # == Get Local Icechunk Repository == #
    config = icechunk.RepositoryConfig.default()
    config.set_virtual_chunk_container(icechunk.VirtualChunkContainer(f"file://{store_fpath}/",
                                                                      icechunk.local_filesystem_store(repo_fpath))
                                                                      )
    if update:
        # Open the existing local Icechunk repository:
        repo = icechunk.Repository.open(
                storage=icechunk.local_filesystem_storage(repo_fpath),
                config=config,
                authorize_virtual_chunk_access={
                    f"file://{store_fpath}/": None
                },
            )
        logger.info(f"Completed: Opened existing local Icechunk repository -> {repo_fpath}")
    else:
        # Create new local Icechunk repository:
        repo = icechunk.Repository.create(
            storage=icechunk.local_filesystem_storage(repo_fpath),
            config=config
        )
        logger.info(f"Completed: Created new local Icechunk repository -> {repo_fpath}")

    # == Write NEMO T/U/V/W/F-grid virtual dataset to Icechunk repository == #
    grid_list = ['gridT',
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
    # File path to `store` directory in which all NEMO AGRIF netCDF output files are included:
    store_fpath = "/gws/ssde/j25a/nemo/vol3/atb299/PROMOTE/u-dy838"

    # Zonal periodicity:
    iperio = True
    # North folding type
    nftype = "T"

    # File path to local Icechunk repository:
    repo_fpath = "/gws/ssde/j25a/nemo/vol3/otooth/PROMOTE/eORCA025_SPNA20/repos/eORCA025_SPNA20_1m"

    for yr in range(1959, 1973):
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
        commit_msg = f"Add PROMOTE eORCA025_SPNA20 monthly NEMODataTree to Icechunk repository ({commit_year_expr})"

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
