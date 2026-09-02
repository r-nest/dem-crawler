This plugin applies a fill algorithm over a DEM raster to extract an altitude mask or a basin area from a set of starting coordinates.

The user can select two directions: upstream or downstream from the starting cell.

It has two modes of operation:
  - connected cells (altitude fill): extracts all downstream or upstream cells connected to the starting cell
  - basin / catchment fill: extracts all downstream or upstream neighboring cells of the starting point.
    Then the next neighboring cells must themselves be either downstream or upstream from the previous candidate cells until the algorithm runs out of candidate cells.

Users input:
  - DEM Raster: the user must choose a raster layer from the drop-down menu or browse a file. 
  - Starting coordinates: the user must indicate a set of coordinates (XX.X,YY.Y [EPSG:SRID]) or click on browse to pick up coordinates with the mouse on the map canvas. 

The CRS of the DEM raster and the set of starting coordinates must match.

The algorithm is placed in the processing toolbox.

