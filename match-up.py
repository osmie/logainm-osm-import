import fiona, csv, shapely
from shapely.geometry import Point, shape
from shapely.ops import transform
import logging
from contextlib import contextmanager
import pyproj
from functools import partial
import xml.etree.ElementTree as ET
import sqlite3


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

def get_logainm_tags(cursor, logainm_id):
    cursor.execute("select logainm_id, name_en, name_ga from names where logainm_id = ?", logainm_id)
    data = cursor.fetchone()
    return {'logainm_id': data[0], 'name_en': data[1], 'name_ga': data[2]}


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

    conn = sqlite3.connect("logainm.sqlite")
    cursor = conn.cursor()

    logger.setLevel(logging.DEBUG)

    boundaries = []
    with printer("reading in OSM shapefiles"):
        for filename, type in [
                    ('townlands/townlands.shp', 'townland'),
                    ('counties/counties.shp', 'county'),
                    ('baronies/baronies.shp', 'barony'),
                    ('civil_parishes/civil_parishes.shp', 'civil_parish'),
            ]:
            with fiona.open(filename, encoding="utf8") as src:
                these_objs = list(src)

            # add geom
            with printer("re-creating geom and transforming for 3857"):
                for t in these_objs:
                    t['geom'] = shape(t['geometry'])
                    t['geom_3857'] = transform(latlon_to_3857, t['geom'])
                    t['type'] = type

            logger.info("Loaded %d %s", len(these_objs), type)
            boundaries.extend(these_objs)
        logger.info("Have %d boundaries", len(boundaries))


    cursor.execute("select 'County '||name_en, logainm_id from names where logainm_category_code = 'CON' and name_en = 'Carlow';")
    logainm_counties = dict(cursor.fetchall())

    for county_name in logainm_counties:
        logger.info("Dealing with %s", county_name)
        osm_county = [b for b in boundaries if b['type'] == 'county' and b['name'] == county_name][0]
        logainm_data = get_logainm_tags(cursor, logainm_counties[county_name])
        logainm_candidates[('relation', str(abs(int(osm_county['properties']['OSM_ID']))))] = logainm_data


    import pdb ; pdb.set_trace()

    # read in OSM XML
    with printer("reading in OSM XML"):
        tree = ET.parse('boundaries.osm.xml')
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
    tree.write("new-boundaries.osm.xml")

main()
