This plugin applies a fill algorithm over a DEM raster to extract an altitude mask or a basin area from a set of starting coordinates.

The user can select two directions: upstream or downstream from the starting cell.

It has two modes of operation:
  - connected cells (altitude fill): extracts all downstream or upstream cells connected to the starting cell
  - basin / catchment fill: extracts all downstream or upstream neighboring cells of the starting point.
    Then the next neighboring cells must themselves be either downstream or upstream from the previous candidate cells until the algorithm runs out of candidate cells.

The CRS of the DEM raster and the set of starting coordinates must match.
