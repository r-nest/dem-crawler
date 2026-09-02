from qgis.core import QgsProcessingProvider
from .algorithms.demcrawler_algorithm import DEMCrawlerAlgorithm

class DEMCrawlerProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(DEMCrawlerAlgorithm())

    def id(self):
        return 'DEMCrawler'

    def name(self):
        return 'DEM Crawler'

    def icon(self):
        return QgsProcessingProvider.icon(self)