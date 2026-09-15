# -*- coding: utf-8 -*-
"""
SVG to QGIS Style
==================

Plugin QGIS per convertire simboli SVG in un file di stile QGIS (.xml).

Questo file viene caricato da QGIS all'avvio del plugin. Non deve importare
nulla al di fuori della libreria standard di Python a livello di modulo,
per garantire un caricamento rapido e sicuro anche quando le dipendenze
PyQGIS non sono ancora completamente inizializzate.
"""


def classFactory(iface):
    """Punto di ingresso richiesto da QGIS.

    :param iface: Interfaccia QGIS (QgisInterface) fornita da QGIS
                   nel momento in cui il plugin viene caricato.
    :type iface: QgisInterface

    :returns: Istanza della classe principale del plugin.
    :rtype: SvgToQgisStyle
    """
    from .svgtoqgisstyle import SvgToQgisStyle
    return SvgToQgisStyle(iface)
