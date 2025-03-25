# pylint: disable=unused-import
import rasterio.mask
import shapely

import dagster as dg
import geopandas as gpd
import numpy as np
import rasterio as rio

from affine import Affine
from jat_slides.partitions import mun_partitions, zone_partitions
from jat_slides.resources import PathResource
from pathlib import Path


YEARS = range(1975, 2021, 5)


def load_built_rasters_factory(year: int) -> dg.OpDefinition:
    @dg.op(
        name=f"load_built_rasters_{year}", out={"data": dg.Out(), "transform": dg.Out()}
    )
    def _op(path_resource: PathResource, bounds: list) -> tuple[np.ndarray, Affine]:
        fpath = Path(path_resource.ghsl_path) / f"BUILT_100/{year}.tif"
        with rio.open(fpath, nodata=65535) as ds:
            data, transform = rio.mask.mask(ds, bounds, crop=True, nodata=0)

        data[data == 65535] = 0

        mask = data[0] >= (100 * 100 * 0.2)
        mask = mask.astype(float)
        mask[mask == 0] = np.nan
        mask *= year

        return mask, transform

    return _op


load_built_rasters_ops = {year: load_built_rasters_factory(year) for year in YEARS}


@dg.op(out=dg.Out(io_manager_key="raster_manager"))
def reduce_rasters(
    rasters: list[np.ndarray], transforms: list[Affine]
) -> tuple[np.ndarray, Affine]:
    arr = np.array(rasters)
    arr = np.nanmin(arr, axis=0)
    arr[np.isnan(arr)] = 0
    arr = arr.astype(int)
    return arr, transforms[0]


@dg.op
def get_total_bounds(
    agebs_1990: gpd.GeoDataFrame,
    agebs_2000: gpd.GeoDataFrame,
    agebs_2010: gpd.GeoDataFrame,
    agebs_2020: gpd.GeoDataFrame,
) -> list:
    geoms = np.concatenate(
        [
            agebs_1990["geometry"].to_numpy(),
            agebs_2000["geometry"].to_numpy(),
            agebs_2010["geometry"].to_numpy(),
            agebs_2020["geometry"].to_numpy(),
        ]
    )
    return [shapely.union_all(geoms)]


@dg.graph
def built_graph(
    agebs_1990: gpd.GeoDataFrame,
    agebs_2000: gpd.GeoDataFrame,
    agebs_2010: gpd.GeoDataFrame,
    agebs_2020: gpd.GeoDataFrame,
) -> tuple[np.ndarray, Affine]:
    bounds = get_total_bounds(agebs_1990, agebs_2000, agebs_2010, agebs_2020)

    rasters, transforms = [], []
    for year in YEARS:
        f = load_built_rasters_ops[year]
        data, transform = f(bounds)
        rasters.append(data)
        transforms.append(transform)

    out = reduce_rasters(rasters, transforms)
    return out


@dg.graph_asset(
    name="built",
    ins={
        "agebs_1990": dg.AssetIn(key=["agebs", "1990"]),
        "agebs_2000": dg.AssetIn(key=["agebs", "2000"]),
        "agebs_2010": dg.AssetIn(key=["agebs", "2010"]),
        "agebs_2020": dg.AssetIn(key=["agebs", "2020"]),
    },
    partitions_def=zone_partitions,
)
def built(
    agebs_1990: gpd.GeoDataFrame,
    agebs_2000: gpd.GeoDataFrame,
    agebs_2010: gpd.GeoDataFrame,
    agebs_2020: gpd.GeoDataFrame,
) -> tuple[np.ndarray, Affine]:
    return built_graph(agebs_1990, agebs_2000, agebs_2010, agebs_2020)


@dg.graph_asset(
    name="built_mun",
    ins={
        "agebs_1990": dg.AssetIn(key=["muns", "1990"]),
        "agebs_2000": dg.AssetIn(key=["muns", "2000"]),
        "agebs_2010": dg.AssetIn(key=["muns", "2010"]),
        "agebs_2020": dg.AssetIn(key=["muns", "2020"]),
    },
    partitions_def=mun_partitions,
)
def built_mun(
    agebs_1990: gpd.GeoDataFrame,
    agebs_2000: gpd.GeoDataFrame,
    agebs_2010: gpd.GeoDataFrame,
    agebs_2020: gpd.GeoDataFrame,
) -> tuple[np.ndarray, Affine]:
    return built_graph(agebs_1990, agebs_2000, agebs_2010, agebs_2020)


@dg.graph_asset(
    name="built_trimmed",
    ins={
        "agebs_1990": dg.AssetIn(key=["agebs_trimmed", "1990"]),
        "agebs_2000": dg.AssetIn(key=["agebs_trimmed", "2000"]),
        "agebs_2010": dg.AssetIn(key=["agebs_trimmed", "2010"]),
        "agebs_2020": dg.AssetIn(key=["agebs_trimmed", "2020"]),
    },
    partitions_def=zone_partitions,
)
def built_trimmed(
    agebs_1990: gpd.GeoDataFrame,
    agebs_2000: gpd.GeoDataFrame,
    agebs_2010: gpd.GeoDataFrame,
    agebs_2020: gpd.GeoDataFrame,
) -> tuple[np.ndarray, Affine]:
    return built_graph(agebs_1990, agebs_2000, agebs_2010, agebs_2020)
