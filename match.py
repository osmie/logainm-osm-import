import sys
import logging
from contextlib import contextmanager
import csv
import sqlite3
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

@contextmanager
def printer(msg):
    msg = msg.strip()
    logger.info("Started "+msg)
    yield
    logger.info("Finished "+msg)

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
    cursor.execute("select logainm_id, name_en, name_ga from names where logainm_id = ?", [logainm_id])
    data = cursor.fetchone()
    return {'logainm_id': data[0], 'name_en': data[1], 'name_ga': data[2]}

def unicodeify_dict(dct):
    for key, value in dct.items():
        dct[key] = value.decode("utf-8")
    return dct

def name_en(obj):
    if obj['NAME_EN'] != '':
        return obj['NAME_EN']
    else:
        return obj['NAME_TAG']

def read_logainm_data():
    results = {}
    for filename, keyname in [('townlands-no-geom.csv', 'townlands'), ('civil_parishes-no-geom.csv', 'civil_parishes'), ('counties-no-geom.csv', 'counties'), ('baronies-no-geom.csv', 'baronies')]:
        with open(filename) as fp:
            reader = csv.DictReader(fp)
            results[keyname] = list(unicodeify_dict(x) for x in reader)

    return results

def osmid_to_logainm_ref(logainm_data, osm_id):
    results = []
    for key in logainm_data.keys():
        results += [x['LOGAINM_RE'] for x in logainm_data[key] if x['OSM_ID'] == osm_id]

    return results[0]

def barony_osmid_for_civil_parish_osmid(logainm_data, civil_parish_id):
    return set(t['BAR_OSM_ID'] for t in logainm_data['townlands'] if t['CP_OSM_ID'] == civil_parish_id and t['BAR_OSM_ID'] != '' )

def parent_osmid_for_obj_osmid(logainm_data, obj_osmid, obj_key, parent_key):
    return set(t[parent_key] for t in logainm_data['townlands'] if t[obj_key] == obj_osmid and t[parent_key] != '' )

def baronies_matchup(logainm_data, cursor):
    return hierachial_matchup(logainm_data, cursor,
                key='baronies', obj_logainm_code="BAR", parent_logainm_code='CON',
                obj_key="BAR_OSM_ID", parent_key="CO_OSM_ID"
         )

def civil_parish_matchup(logainm_data, cursor):
    return hierachial_matchup(logainm_data, cursor,
                key='civil_parishes', obj_logainm_code="PAR", parent_logainm_code='BAR',
                obj_key="CP_OSM_ID", parent_key="BAR_OSM_ID"
         )

def townlands_matchup(logainm_data, cursor):
    return hierachial_matchup(logainm_data, cursor,
                key='townlands', obj_logainm_code="BF", parent_logainm_code='PAR',
                obj_key="OSM_ID", parent_key="CP_OSM_ID"
         )

def hierachial_matchup(logainm_data, cursor, key, obj_logainm_code, parent_logainm_code, obj_key, parent_key):
    logger.info("Have %d %s in total", len(logainm_data[key]), key)
    results = {}

    possibles = [b for b in logainm_data[key] if b['LOGAINM_RE'] == '']
    logger.info("Found %d %s without logainm ref", len(possibles), key)

    for obj in possibles:
        parent_osm_id = parent_osmid_for_obj_osmid(logainm_data, obj['OSM_ID'], obj_key, parent_key)
        if len(parent_osm_id) == 0:
            logger.debug("No parent found for obj %s (%s)", name_en(obj), obj['OSM_ID'])
            continue
        elif len(parent_osm_id) > 1:
            logger.debug("Found %d (%s) parents for obj %s (%s)", len(parent_osm_id), ",".join(parent_osm_id), name_en(obj), obj['OSM_ID'])
            continue
        elif len(parent_osm_id) == 1:
            parent_osm_id = parent_osm_id.pop()
            try:
                parent_logainm_id = osmid_to_logainm_ref(logainm_data, parent_osm_id)
                logger.debug("obj %s is in parent %s which is logainm id %s", name_en(obj), parent_osm_id, parent_logainm_id)
            except IndexError:
                logger.debug("obj %s is in parent %s which has no known logainm", name_en(obj), parent_osm_id)
                continue
        else:
            assert False

        # Now we have the logainm ref of the parent that this CP is in.
        # Look at the logainm data for the CPs in that bar
        cursor.execute("select obj.logainm_id from names as parent join geometric_contains as con on (parent.logainm_id = con.outer_obj_id) join names as obj on (obj.logainm_id = con.inner_obj_id) where parent.logainm_category_code = ? and obj.logainm_category_code = ? and parent.logainm_id = ? and obj.name_en = ?;", [parent_logainm_code, obj_logainm_code, parent_logainm_id, name_en(obj)])
        data = cursor.fetchall()
        if len(data) == 0:
            logger.debug("Found no logainm data for parent")
        elif len(data) > 1:
            logger.debug("Found >1 obj logainm ids")
        elif len(data) == 1:
            logger.debug("Found logainm id %s", data[0][0])
            # remove leading '-' character
            results[('relation', obj['OSM_ID'][1:])] = get_logainm_tags(cursor, data[0][0])
        else:
            assert False


    logger.info("Found %d candidates", len(results))
    return results


def main():

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    conn = sqlite3.connect("logainm.sqlite")
    cursor = conn.cursor()

    logger.setLevel(logging.INFO)

    logainm_data = read_logainm_data()

    logainm_candidates = {}

    logainm_candidates.update(baronies_matchup(logainm_data, cursor))

    #logainm_candidates.update(civil_parish_matchup(logainm_data, cursor))
    #logainm_candidates.update(townlands_matchup(logainm_data, cursor))

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
    tree.write("new-boundaries.osm.xml", encoding='utf-8', xml_declaration=True) 

if __name__ == '__main__':
    main()


