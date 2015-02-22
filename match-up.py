import fiona, csv, shapely
from shapely.geometry import Point, shape
from shapely.ops import transform
import logging
from contextlib import contextmanager
import pyproj
from functools import partial
import xml.etree.ElementTree as ET


logger = logging.getLogger(__name__)

latlon_to_3857 = partial(
    pyproj.transform,
    pyproj.Proj(init="epsg:4326"),
    pyproj.Proj(init="epsg:3857") )

@contextmanager
def printer(msg):
    msg = msg.strip()
    logger.info("Started "+msg)
    yield
    logger.info("Finished "+msg)

def dist(poly, point):
    if poly.intersects(point):
        return 0
    else:
        return poly.distance(point)/1000

def candidate_logainm_ids(townland, logainms):
    name = townland['properties']['NAME']
    same_name = [l for l in logainms if l['name_en'] == name]
    dists = [dist(townland['geom_3857'], l['point_3857']) for l in same_name]
    logger.debug("Got %d logainms for %s dists: %r", len(same_name), name, dists)

    return same_name

def get_existing_osm_tags(xml_el):
    return {el.get('k'): el.get('v') for el in xml_el.findall("tag")}


def logainm_tags(xml_el, logainm_data):
    tags = get_existing_osm_tags(xml_el)
    new_tags = {
        'logainm:ref': logainm_data['logainm_id'],
        'logainm:url': 'http://www.logainm.ie/{}'.format(logainm_data['logainm_id'])
    }

    if 'name:ga' not in tags:
        new_tags['name:ga'] = logainm_data['name_ga']
    else:
        if tags['name:ga'] != logainm_data['name_ga']:
            new_tags['offical_name:ga'] = logainm_data['name_ga']

    if 'name:en' not in tags:
        new_tags['name:en'] = logainm_data['name_en']
    else:
        if tags['name:en'] != logainm_data['name_en']:
            new_tags['offical_name:en'] = logainm_data['name_en']



def main():

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    logger.setLevel(logging.DEBUG)

    with printer("reading in OSM shapefile"):
        with fiona.open("townlands/townlands.shp") as src:
            townlands = list(src)

        # add geom
        with printer("re-creating geom and transforming for 3857"):
            for t in townlands:
                t['geom'] = shape(t['geometry'])
                t['geom_3857'] = transform(latlon_to_3857, t['geom'])

    with printer("reading in Logainm CSV"):
        with open("logainm-csvs/townlands.csv") as csvfp:
            reader = csv.DictReader(csvfp)
            logainms = list(reader)
        
        # Add point object
        for l in logainms:
            l['point'] = Point((float(l['lon']), float(l['lat'])))
            l['point_3857'] = transform(latlon_to_3857, l['point'])

    # match up OSM & Logainm
    with printer("matching up"):
        logainm_candidates = {}
        for townland in townlands[:5]:
            logger.debug("Looking at townland name %s osm_id %s", townland['properties']['NAME'], townland['properties']['OSM_ID'])
            candidates = candidate_logainm_ids(townland, logainms)
            if len(candidates) == 0:
                logger.info("No results for %s", townland['properties']['NAME'])
            elif len(candidates) == 1:
                logger.info("Got a result for %s", townland['properties']['NAME'])
                logainm_candidates[('relation', str(abs(int(townland['properties']['OSM_ID']))))] = candidates[0]
            else:
                logger.info("Got >1 results for %s", townland['properties']['NAME'])


    # read in OSM XML
    with printer("reading in OSM XML"):
        tree = ET.parse('townlands.osm.xml')
        root = tree.getroot()

    # add new tags to OSM XML
    with printer("adding XML tags"):
        for rel in root.iter("relation"):
            osm_id = rel.get("id", None)
            #logger.debug("OSM ID %r", osm_id)
            if ('relation', osm_id) in logainm_candidates:
                logging.debug("Adding tags to OSM_ID %d", osm_id)
                logaimn_data = logainm_candidates[('relation', osm_id)]
                for k, v in logainm_tags(rel, logaimn_data).items():
                    ET.SubElement(rel, 'tag', {'k': k, 'v': v})


    # write out OSM XML
    tree.write("new-townlands.osm.xml")

main()
