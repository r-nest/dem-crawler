from collections import deque
import numpy as np

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterPoint,
    QgsProcessingParameterEnum,
    QgsProcessingParameterRasterDestination,
    QgsCoordinateTransform,
    QgsProject,
    QgsMessageLog,
    Qgis
)

class DEMCrawlerAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTER = 'INPUT_RASTER'
    START_POINT = 'START_POINT'
    MODE = 'MODE'
    DIRECTION = 'DIRECTION'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'DEMCrawler'

    def displayName(self):
        return 'DEM Crawler'

    def group(self):
        return 'Terrain Analysis'

    def groupId(self):
        return 'terrain_analysis'

    def createInstance(self):
        return DEMCrawlerAlgorithm()

    def initAlgorithm(self, config=None):
        # 1. Widget Menu déroulant + Chercher fichier pour les couches Raster
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_RASTER,
                'Input DEM Raster'
            )
        )

        # 2. Widget Point avec bouton "Cliquer sur le canevas cartographique"
        self.addParameter(
            QgsProcessingParameterPoint(
                self.START_POINT,
                'Start coordinates (click browse to pick up coordinates from the map canvas)'
            )
        )

        # 3. Sélection du mode d'algorithme
        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE,
                'Operation mode',
                options=['Connected cells (altitude fill)', 'Basin / Catchment (basin fill)'],
                defaultValue=1
            )
        )

        # 4. Direction (Upstream / Downstream)
        self.addParameter(
            QgsProcessingParameterEnum(
                self.DIRECTION,
                'Flow direction',
                options=['Downstream', 'Upstream'],
                defaultValue=0
            )
        )

        # 5. Widget de destination du raster (couche temporaire par défaut + bouton enregistrer)
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                'Output Raster'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        raster_layer = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        point = self.parameterAsPoint(parameters, self.START_POINT, context, raster_layer.crs())
        mode_idx = self.parameterAsEnum(parameters, self.MODE, context)
        dir_idx = self.parameterAsEnum(parameters, self.DIRECTION, context)
        output_file = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        if raster_layer is None or not raster_layer.isValid():
            raise Exception("Invalid raster layer provided.")

        # Transformation du SRC / CRS du point vers le SRC du Raster
        point_crs = self.parameterAsPointCrs(parameters, self.START_POINT, context)
        raster_crs = raster_layer.crs()

        if point_crs.isValid() and point_crs != raster_crs:
            feedback.pushInfo(f"Reprojecting coordinates from {point_crs.authid()} to {raster_crs.authid()}...")
            transform = QgsCoordinateTransform(point_crs, raster_crs, QgsProject.instance())
            point = transform.transform(point)

        # Vérification des limites spatiales
        extent = raster_layer.extent()
        if not extent.contains(point):
            raise Exception(f"Input coordinates CRS and raster CRS do not match or point is outside raster bounds. Point: ({point.x()}, {point.y()})")

        # Conversion des coordonnées X,Y du point en indices Col, Row
        res_x = raster_layer.rasterUnitsPerPixelX()
        res_y = raster_layer.rasterUnitsPerPixelY()
        
        col = int((point.x() - extent.xMinimum()) / res_x)
        row = int((extent.yMaximum() - point.y()) / res_y)

        # Lecture du raster via la couche
        provider = raster_layer.dataProvider()
        block = provider.block(1, extent, raster_layer.width(), raster_layer.height())
        
        # Convertir la matrice du bloc en NumPy Array
        from osgeo import gdal
        ds = gdal.Open(raster_layer.source())
        dem_array = ds.GetRasterBand(1).ReadAsArray()

        in_type = "downstream" if dir_idx == 0 else "upstream"

        # Execution du calcul
        feedback.pushInfo(f"Running algorithm starting at pixel col={col}, row={row}...")
        
        if mode_idx == 0:
            out_array = self.altitude_fill(dem_array, col, row, in_type, feedback)
        else:
            out_array = self.basin_fill(dem_array, col, row, in_type, feedback)

        # --- Écriture du Raster de sortie ---
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(output_file, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Float32)
        out_ds.SetGeoTransform(ds.GetGeoTransform())
        out_ds.SetProjection(ds.GetProjection())
        
        band = out_ds.GetRasterBand(1)
        band.WriteArray(out_array)
        band.SetNoDataValue(np.nan)
        band.FlushCache()
        out_ds = None
        ds = None

        return {self.OUTPUT: output_file}

    def basin_fill(self, inArray, c, r, inType="downstream", feedback=None):
        height, width = inArray.shape
        
        if not (0 <= c < width and 0 <= r < height):
            raise ValueError("Coordinates are outside raster bounds.")

        is_downstream = (inType == "downstream")
        thr = inArray[r, c]

        if np.isnan(thr):
            return np.full_like(inArray, np.nan)

        outArray = np.full_like(inArray, np.nan)
        visited = np.zeros((height, width), dtype=bool)

        queue = deque([(c, r)])
        visited[r, c] = True

        offsets = [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]

        while queue:
            if feedback and feedback.isCanceled():
                break

            x, y = queue.popleft()
            curr_val = inArray[y, x]
            outArray[y, x] = curr_val

            for dx, dy in offsets:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if not visited[ny, nx] and not np.isnan(inArray[ny, nx]):
                        val = inArray[ny, nx]
                        cond = (val <= curr_val) if is_downstream else (val >= curr_val)
                        if cond:
                            visited[ny, nx] = True
                            queue.append((nx, ny))

        return outArray

    def altitude_fill(self, inArray, c, r, inType="downstream", feedback=None):
        height, width = inArray.shape

        if not (0 <= c < width and 0 <= r < height):
            raise ValueError("Coordinates are outside raster bounds.")

        is_downstream = (inType == "downstream")
        thr = inArray[r, c]

        if np.isnan(thr):
            return np.full_like(inArray, np.nan)

        outArray = np.full_like(inArray, np.nan)
        visited = np.zeros((height, width), dtype=bool)

        queue = deque([(c, r)])
        visited[r, c] = True

        offsets = [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]

        while queue:
            if feedback and feedback.isCanceled():
                break

            x, y = queue.popleft()
            outArray[y, x] = inArray[y, x]

            for dx, dy in offsets:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if not visited[ny, nx] and not np.isnan(inArray[ny, nx]):
                        val = inArray[ny, nx]
                        cond = (val <= thr) if is_downstream else (val >= thr)
                        if cond:
                            visited[ny, nx] = True
                            queue.append((nx, ny))

        return outArray
