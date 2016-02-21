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

def read_logainm_data():
    results = {}
    for filename, keyname in [('townlands-no-geom.csv', 'townlands'), ('civil_parishes-no-geom.csv', 'civil_parishes'), ('counties-no-geom.csv', 'counties'), ('baronies-no-geom.csv', 'baronies')]:
        with open(filename) as fp:
            reader = csv.DictReader(fp)
            results[keyname] = list(reader)

    return results

def osmid_to_logainm_ref(logainm_data, osm_id):
    results = []
    for key in logainm_data.keys():
        results += [x['LOGAINM_RE'] for x in logainm_data[key] if x['OSM_ID'] == osm_id]

    return results[0]

def barony_osmid_for_civil_parish_osmid(logainm_data, civil_parish_id):
    return set(t['BAR_OSM_ID'] for t in logainm_data['townlands'] if t['CP_OSM_ID'] == civil_parish_id and t['BAR_OSM_ID'] != '' )

def baronies_matchup(logainm_data):
    logger.info("Have %d baronies", len(logainm_data['baronies']))
    results = {}

    possible_baronies = [b for b in logainm_data['baronies'] if b['LOGAINM_RE'] == '']
    logger.info("Found %d baronies without logainm ref", len(possible_baronies))

    for barony in possible_baronies:
        county_osm_id = barony['CO_OSM_ID']
        try:
            county_logainm_id = osmid_to_logainm_ref(logainm_data, county_osm_id)
            logger.info("Barony %s is in county %s (%s) which is logainm is %s", barony['NAME_TAG'], barony['CO_NAME'], barony['CO_OSM_ID'], county_logainm_id)
        except:
            logger.info("Barony %s is in county %s (%s) which has no known logainm", barony['NAME_TAG'], barony['CO_NAME'], barony['CO_OSM_ID'])


    return results

def civil_parish_matchup(logainm_data, cursor):
    logger.info("Have %d civil parishes", len(logainm_data['civil_parishes']))
    results = {}

    possible_civil_parishes = [b for b in logainm_data['civil_parishes'] if b['LOGAINM_RE'] == '']
    logger.info("Found %d civil_parishes without logainm ref", len(possible_civil_parishes))

    for civil_parish in possible_civil_parishes:
        barony_osm_id = barony_osmid_for_civil_parish_osmid(logainm_data, civil_parish['OSM_ID'])
        if len(barony_osm_id) == 0:
            logger.info("No barony found for CP %s (%s)", civil_parish['NAME_TAG'], civil_parish['OSM_ID'])
            continue
        elif len(barony_osm_id) > 1:
            logger.info("Found %d (%s) baronies for CP %s (%s)", len(barony_osm_id), ",".join(barony_osm_id), civil_parish['NAME_TAG'], civil_parish['OSM_ID'])
            continue
        elif len(barony_osm_id) == 1:
            barony_osm_id = barony_osm_id.pop()
            try:
                barony_logainm_id = osmid_to_logainm_ref(logainm_data, barony_osm_id)
                logger.info("civil_parish %s is in barony %s which is logainm id %s", civil_parish['NAME_TAG'], barony_osm_id, barony_logainm_id)
            except IndexError:
                logger.info("civil_parish %s is in barony %s which has no known logainm", civil_parish['NAME_TAG'], barony_osm_id)
                continue
        else:
            assert False

        # Now we have the logainm ref of the barony that this CP is in.
        # Look at the logainm data for the CPs in that bar



    return results

    

def main():

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    conn = sqlite3.connect("../logainm.sqlite")
    cursor = conn.cursor()

    logger.setLevel(logging.DEBUG)

    logainm_data = read_logainm_data()

    logainm_candidates = {}

    #logainm_candidates.update(baronies_matchup(logainm_data))
    logainm_candidates.update(civil_parish_matchup(logainm_data, cursor))
    return

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


