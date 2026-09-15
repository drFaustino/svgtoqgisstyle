# -*- coding: utf-8 -*-
"""
Funzioni di supporto, indipendenti dalla GUI, per:

  - individuare i file SVG in una cartella (ricorsivamente);
  - renderizzare un'anteprima raster (QPixmap) da un contenuto SVG;
  - applicare colori personalizzati di "sfondo" e "riempimento" al testo SVG,
    con un approccio euristico basato sull'ordine di comparsa dei valori
    "fill" nel documento (il primo colore trovato è considerato "sfondo",
    quelli successivi "riempimento");
  - costruire il file di stile QGIS (.xml) a partire da un elenco di simboli.

Limiti noti (euristica di ricolorazione):
  Il riconoscimento di "sfondo" e "riempimento" si basa sull'ordine di
  comparsa degli attributi/proprietà "fill" nel markup SVG e non su
  un'analisi semantica della struttura grafica. Funziona bene con la
  maggior parte delle icone "a due colori" (es. forma di sfondo + simbolo),
  ma SVG molto complessi con molti colori distinti potrebbero non essere
  ricolorati come atteso: in quel caso solo il primo colore incontrato
  viene trattato come "sfondo" e TUTTI gli altri come "riempimento".
"""

import os
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

from qgis.PyQt.QtCore import Qt, QByteArray, QSize
from qgis.PyQt.QtGui import QPixmap, QPainter, QColor
from qgis.PyQt.QtSvg import QSvgRenderer


SVG_EXTENSION = '.svg'


# --------------------------------------------------------------------------- #
# Ricerca file SVG
# --------------------------------------------------------------------------- #
def find_svg_files(folder):
    """Cerca ricorsivamente tutti i file .svg all'interno di una cartella.

    :param folder: percorso della cartella da esplorare.
    :type folder: str
    :returns: elenco ordinato di percorsi assoluti ai file .svg trovati.
    :rtype: list[str]
    """
    found = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(SVG_EXTENSION):
                found.append(os.path.join(root, f))
    found.sort(key=lambda p: p.lower())
    return found


# --------------------------------------------------------------------------- #
# Rendering anteprima
# --------------------------------------------------------------------------- #
def render_svg_pixmap(svg_text, size=64):
    """Renderizza il testo SVG fornito in un QPixmap quadrato trasparente.

    :param svg_text: contenuto testuale del file SVG.
    :type svg_text: str
    :param size: lato (in pixel) del pixmap quadrato di anteprima.
    :type size: int
    :returns: pixmap risultante (trasparente/vuoto se il contenuto non è
              un SVG valido).
    :rtype: QPixmap
    """
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)

    try:
        data = QByteArray(svg_text.encode('utf-8'))
    except Exception:
        return pixmap

    renderer = QSvgRenderer(data)
    if not renderer.isValid():
        return pixmap

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter)
    finally:
        painter.end()

    return pixmap


# --------------------------------------------------------------------------- #
# Ricolorazione
# --------------------------------------------------------------------------- #
_FILL_ATTR_RE = re.compile(r'fill\s*=\s*"([^"]*)"', re.IGNORECASE)
_STYLE_FILL_RE = re.compile(r'fill\s*:\s*([^;"\']+)', re.IGNORECASE)

_IGNORED_FILL_VALUES = ('none', 'transparent', '')


def extract_fill_values(svg_text):
    """Restituisce l'elenco ordinato (senza duplicati) dei valori "fill"
    presenti nel documento SVG, nell'ordine in cui compaiono.

    :param svg_text: contenuto testuale del file SVG.
    :type svg_text: str
    :rtype: list[str]
    """
    values = []
    # Uniamo le posizioni di attributi fill="" e proprietà fill: dentro style=""
    matches = []
    for m in _FILL_ATTR_RE.finditer(svg_text):
        matches.append((m.start(), m.group(1).strip()))
    for m in _STYLE_FILL_RE.finditer(svg_text):
        matches.append((m.start(), m.group(1).strip()))
    matches.sort(key=lambda t: t[0])

    for _pos, value in matches:
        if value.lower() in _IGNORED_FILL_VALUES:
            continue
        if value not in values:
            values.append(value)
    return values


def _replace_fill_value(svg_text, old_value, new_hex):
    """Sostituisce tutte le occorrenze di un valore fill specifico (sia come
    attributo fill="..." sia come proprietà fill:... in uno style) con il
    nuovo colore, lasciando invariato il resto del documento.
    """
    old_escaped = re.escape(old_value)

    svg_text = re.sub(
        r'(fill\s*=\s*")' + old_escaped + r'(")',
        r'\g<1>' + new_hex + r'\g<2>',
        svg_text,
        flags=re.IGNORECASE,
    )
    svg_text = re.sub(
        r'(fill\s*:\s*)' + old_escaped + r'(\s*;?)',
        r'\g<1>' + new_hex + r'\g<2>',
        svg_text,
        flags=re.IGNORECASE,
    )
    return svg_text


def recolor_svg_text(svg_text, bg_hex=None, fg_hex=None):
    """Applica il colore di sfondo e/o di riempimento al testo SVG.

    Il "colore di sfondo" viene associato al primo valore fill incontrato nel
    documento; il "colore di riempimento" viene associato a tutti i valori
    fill successivi e diversi dal primo (vedi note euristiche in cima al
    modulo).

    :param svg_text: contenuto SVG originale.
    :param bg_hex: colore di sfondo in formato "#rrggbb" (o None per non
                   modificarlo).
    :param fg_hex: colore di riempimento in formato "#rrggbb" (o None per
                   non modificarlo).
    :returns: nuovo contenuto SVG con i colori sostituiti.
    :rtype: str
    """
    if not bg_hex and not fg_hex:
        return svg_text

    values = extract_fill_values(svg_text)
    if not values:
        return svg_text

    result = svg_text
    bg_value = values[0]
    fg_values = values[1:]

    if bg_hex:
        result = _replace_fill_value(result, bg_value, bg_hex)

    if fg_hex:
        for v in fg_values:
            result = _replace_fill_value(result, v, fg_hex)

    return result


def qcolor_to_hex(qcolor):
    """Converte un QColor in stringa esadecimale "#rrggbb" (senza alpha)."""
    return qcolor.name(QColor.NameFormat.HexRgb)


def qcolor_to_qgis_rgba(qcolor):
    """Converte un QColor nel formato "r,g,b,a" usato dalle opzioni di
    stile QGIS.
    """
    return '{},{},{},{}'.format(
        qcolor.red(), qcolor.green(), qcolor.blue(), qcolor.alpha()
    )


# --------------------------------------------------------------------------- #
# Generazione file di stile QGIS
# --------------------------------------------------------------------------- #
def sanitize_symbol_name(name):
    """Ripulisce un nome file per l'uso come nome del simbolo di stile.

    Mantiene lettere, cifre, spazi, trattini e underscore; tutto il resto
    viene sostituito con underscore.
    """
    cleaned = re.sub(r'[^\w\- ]+', '_', name, flags=re.UNICODE)
    cleaned = cleaned.strip() or 'symbol'
    return cleaned


def unique_symbol_name(base_name, used_names):
    """Garantisce un nome di simbolo univoco all'interno del file di stile,
    aggiungendo un suffisso numerico progressivo in caso di collisione.
    """
    name = base_name
    counter = 1
    while name in used_names:
        counter += 1
        name = '{}_{}'.format(base_name, counter)
    used_names.add(name)
    return name


def build_svg_marker_symbol_element(name, svg_path, fill_rgba, outline_rgba,
                                     outline_width='0.2', size='6'):
    """Costruisce l'elemento XML <symbol> (marker SvgMarker) per un simbolo.

    :param name: nome univoco del simbolo all'interno del file di stile.
    :param svg_path: percorso (assoluto, con separatori "/") al file SVG
                      referenziato dal simbolo.
    :param fill_rgba: colore di riempimento in formato "r,g,b,a".
    :param outline_rgba: colore di contorno in formato "r,g,b,a".
    :param outline_width: spessore del contorno in millimetri (stringa).
    :param size: dimensione del simbolo in millimetri (stringa).
    :rtype: xml.etree.ElementTree.Element
    """
    symbol_el = ET.Element('symbol', {
        'name': name,
        'type': 'marker',
        'alpha': '1',
        'clip_to_extent': '1',
        'force_rhr': '0',
    })

    # Blocco data_defined_properties minimo, richiesto dal formato QGIS
    ddp = ET.SubElement(symbol_el, 'data_defined_properties')
    ddp_option = ET.SubElement(ddp, 'Option', {'type': 'Map'})
    ET.SubElement(ddp_option, 'Option', {'name': 'name', 'type': 'QString', 'value': ''})
    ET.SubElement(ddp_option, 'Option', {'name': 'properties'})
    ET.SubElement(ddp_option, 'Option', {'name': 'type', 'type': 'QString', 'value': 'collection'})

    layer_el = ET.SubElement(symbol_el, 'layer', {
        'pass': '0',
        'class': 'SvgMarker',
        'locked': '0',
        'enabled': '1',
    })
    opt_map = ET.SubElement(layer_el, 'Option', {'type': 'Map'})

    def add_option(opt_name, opt_value):
        ET.SubElement(opt_map, 'Option', {
            'type': 'QString', 'name': opt_name, 'value': opt_value
        })

    add_option('alpha', '1')
    add_option('angle', '0')
    add_option('color', fill_rgba)
    add_option('fixedAspectRatio', '0')
    add_option('horizontal_anchor_point', '1')
    add_option('name', svg_path)
    add_option('offset', '0,0')
    add_option('offset_map_unit_scale', '3x:0,0,0,0,0,0')
    add_option('offset_unit', 'MM')
    add_option('outline_color', outline_rgba)
    add_option('outline_width', outline_width)
    add_option('outline_width_map_unit_scale', '3x:0,0,0,0,0,0')
    add_option('outline_width_unit', 'MM')
    add_option('scale_method', 'diameter')
    add_option('size', size)
    add_option('size_map_unit_scale', '3x:0,0,0,0,0,0')
    add_option('size_unit', 'MM')
    add_option('vertical_anchor_point', '1')

    return symbol_el


def build_style_document(symbol_elements):
    """Costruisce il documento XML completo <qgis_style> a partire da un
    elenco di elementi <symbol> già pronti.

    :param symbol_elements: elenco di Element <symbol>.
    :returns: stringa XML formattata (pretty-printed), pronta per essere
              scritta su file.
    :rtype: str
    """
    root = ET.Element('qgis_style', {'version': '2'})
    symbols_el = ET.SubElement(root, 'symbols')
    for el in symbol_elements:
        symbols_el.append(el)

    rough_string = ET.tostring(root, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty = reparsed.toprettyxml(indent='  ', encoding='UTF-8').decode('utf-8')

    # Rimuove le righe vuote che toprettyxml tende ad aggiungere
    lines = [line for line in pretty.splitlines() if line.strip()]

    # Aggiunge il DOCTYPE atteso da QGIS per i file di stile
    if lines and lines[0].startswith('<?xml'):
        lines.insert(1, '<!DOCTYPE qgis_style>')

    return '\n'.join(lines) + '\n'
