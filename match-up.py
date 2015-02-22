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

def single_exact_name_and_name_ga_match_and_inside(townland, logainms):
    name = townland['properties'].get('NAME')
    name_ga = townland['properties'].get('NAME:GA')
    if name_ga is None:
        return None

    same_name = [l for l in logainms if l['name_en'] == name and l['name_ga'] == name_ga]

    if len(same_name) == 1 and townland['geom_3857'].intersects(same_name[0]['point_3857']):
        return same_name[0]
    else:
        return None

def single_exact_name_and_optional_name_ga_match_and_inside(townland, logainms):
    name = townland['properties'].get('NAME')
    name_ga = townland['properties'].get('NAME:GA')

    if name_ga:
        same_name = [l for l in logainms if l['name_en'] == name and l['name_ga'] == name_ga]
    else:
        same_name = [l for l in logainms if l['name_en'] == name]

    if len(same_name) == 1 and townland['geom_3857'].intersects(same_name[0]['point_3857']):
        return same_name[0]
    else:
        return None

def name_and_optional_name_ga_match_very_near(townland, logainms):
    name = townland['properties'].get('NAME')
    name_ga = townland['properties'].get('NAME:GA')

    if name_ga:
        same_name = [l for l in logainms if l['name_en'] == name and l['name_ga'] == name_ga]
    else:
        same_name = [l for l in logainms if l['name_en'] == name]

    dists = [dist(townland['geom_3857'], l['point_3857']) for l in same_name]
    logger.info(dists)
    if sum(1 for x in dist if x == 0) == 1 and len(x for x in dist is x > 20) == len(dists) - 1:
        for dist, l in zip(dists, same_name):
            if dist == 0:
                return l

    return None


def get_existing_osm_tags(xml_el):
    """Given a XML element for an object, return (as dict) the current OSM tags"""
    return {el.get('k'): el.get('v') for el in xml_el.findall("tag")}


def logainm_tags(xml_el, logainm_data):
    """Given an XML element for an OSM object, return (as dict) the tags to add
    to it, presuming it is to be matched up to this logainm_data"""
    tags = get_existing_osm_tags(xml_el)
    new_tags = {
        'logainm:ref': logainm_data['logainm_id'],
        'logainm:url': 'http://www.logainm.ie/en/{}'.format(logainm_data['logainm_id'])
    }

    if logainm_data['name_ga'] not in ["", None]:
        if 'name:ga' not in tags:
            new_tags['name:ga'] = logainm_data['name_ga']
        else:
            if tags['name:ga'] != logainm_data['name_ga']:
                new_tags['offical_name:ga'] = logainm_data['name_ga']

    if logainm_data['name_en'] not in ["", None]:
        if 'name:en' not in tags:
            new_tags['name:en'] = logainm_data['name_en']
        else:
            if tags['name:en'] != logainm_data['name_en']:
                new_tags['offical_name:en'] = logainm_data['name_en']

    return new_tags

def match_up_pass(townlands, logainms, matching_function):
    logainm_candidates = {}
    unmatched_townlands = []
    for townland in townlands:
        #logger.debug("Looking at townland name %s osm_id %s", townland['properties']['NAME'], townland['properties']['OSM_ID'])
        candidate = matching_function(townland, logainms)
        if candidate:
            logainm_candidates[('relation', str(abs(int(townland['properties']['OSM_ID']))))] = candidate
        else:
            unmatched_townlands.append(townland)

    return logainm_candidates, unmatched_townlands


def main():

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    logger.setLevel(logging.DEBUG)

    with printer("reading in OSM shapefile"):
        with fiona.open("townlands/townlands.shp", encoding="utf8") as src:
            townlands = list(src)

        # add geom
        with printer("re-creating geom and transforming for 3857"):
            for t in townlands:
                t['geom'] = shape(t['geometry'])
                t['geom_3857'] = transform(latlon_to_3857, t['geom'])

        logger.info("Loaded %d townlands", len(townlands))

    with printer("reading in Logainm CSV"):
        with open("logainm-csvs/townlands.csv") as csvfp:
            reader = csv.DictReader(csvfp)
            logainms = list(reader)
        
        # Add point object
        for l in logainms:
            l['point'] = Point((float(l['lon']), float(l['lat'])))
            l['point_3857'] = transform(latlon_to_3857, l['point'])
            l['name_ga'] = l['name_ga'].decode("utf8")

        logger.info("Loaded %d Logainm rows", len(logainms))

    #import pdb ; pdb.set_trace()

    # match up OSM & Logainm
    with printer("matching up"):
        logainm_candidates = {}

        for func in [
                    single_exact_name_and_name_ga_match_and_inside,
                    single_exact_name_and_optional_name_ga_match_and_inside,
                    name_and_optional_name_ga_match_very_near,
                ]:
            name = func.__name__
            new_logainm_candidates, new_townlands = match_up_pass(townlands, logainms, func)
            logainm_candidates.update(new_logainm_candidates)
            logger.info("Matched up %d townlands with %s, only %d left", len(townlands) - len(new_townlands), name, len(new_townlands))
            townlands = new_townlands


    # read in OSM XML
    with printer("reading in OSM XML"):
        tree = ET.parse('townlands.osm.xml')
        root = tree.getroot()

    # add new tags to OSM XML
    with printer("adding XML tags"):
        for rel in root.iter("relation"):
            osm_id = rel.get("id", None)
            if ('relation', osm_id) in logainm_candidates:
                logging.debug("Adding tags to OSM_ID %d", osm_id)
                logaimn_data = logainm_candidates[('relation', osm_id)]
                for k, v in logainm_tags(rel, logaimn_data).items():
                    ET.SubElement(rel, 'tag', {'k': k, 'v': v})


    # write out OSM XML
    tree.write("new-townlands.osm.xml")

main()
