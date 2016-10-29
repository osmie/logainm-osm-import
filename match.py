import sys
import logging
from contextlib import contextmanager
import csv
import sqlite3
import xml.etree.ElementTree as ET
import argparse
from collections import defaultdict


logger = logging.getLogger(__name__)

@contextmanager
def printer(msg):
    msg = msg.strip()
    logging.info("Started "+msg)
    yield
    logging.info("Finished "+msg)

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

    # Not adding official_name:XX tags because that is not accurate for NI.

    if logainm_data['name_ga'] not in ["", None]:
        if 'name:ga' not in tags:
            new_tags['name:ga'] = logainm_data['name_ga']
        else:
            pass
            #if tags['name:ga'] != logainm_data['name_ga']:
            #    new_tags['official_name:ga'] = logainm_data['name_ga']

    if logainm_data['name_en'] not in ["", None]:
        if 'name:en' not in tags:
            new_tags['name:en'] = logainm_data['name_en']
        else:
            pass
            #if tags['name:en'] != logainm_data['name_en']:
            #    new_tags['official_name:en'] = logainm_data['name_en']

    #if 'official_name:en' not in tags:
    #    new_tags['official_name:en'] = logainm_data['name_en']

    #if 'official_name:ga' not in tags:
    #    new_tags['official_name:ga'] = logainm_data['name_ga']

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
    data_to_load = [('townlands-no-geom.csv', 'townlands'), ('civil_parishes-no-geom.csv', 'civil_parishes'), ('counties-no-geom.csv', 'counties'), ('baronies-no-geom.csv', 'baronies')]
    for filename, keyname in data_to_load:
        with open(filename) as fp:
            reader = csv.DictReader(fp)
            results[keyname] = list(unicodeify_dict(x) for x in reader)

    # create a dict
    results['index'] = {}
    for obj_key in  ['OSM_ID', 'BAR_OSM_ID', 'CP_OSM_ID']:
        results['index'][obj_key] = {}
        for parent_key in  ['BAR_OSM_ID', 'CP_OSM_ID', 'CO_OSM_ID']:
            results['index'][obj_key][parent_key] = defaultdict(set)

    for t in results['townlands']:
        for obj_key in  ['OSM_ID', 'BAR_OSM_ID', 'CP_OSM_ID']:
            for parent_key in  ['BAR_OSM_ID', 'CP_OSM_ID', 'CO_OSM_ID']:
                if t[parent_key] != '':
                    results['index'][obj_key][parent_key][t[obj_key]].add(t[parent_key])

    results['index']['osmid_to_logainm_ref'] = {}
    for filename, keyname in data_to_load:
        for x in results[keyname]:
            if x['LOGAINM_RE'].strip() not in (None, ''):
                results['index']['osmid_to_logainm_ref'][x['OSM_ID']] = x['LOGAINM_RE']

    return results

def osmid_to_logainm_ref(logainm_data, osm_id, existing_match_ups):
    try:
        result = logainm_data['index']['osmid_to_logainm_ref'][osm_id]
    except (KeyError, IndexError):
        # is this already seen on a higher level match up?
        # [1:] to remove the -
        result = existing_match_ups[('relation', osm_id[1:])]['logainm_id']
        logger.debug("Found a Logainm id (%s) for %s based on a previous match up", result, osm_id)
    return result

def barony_osmid_for_civil_parish_osmid(logainm_data, civil_parish_id):
    return set(t['BAR_OSM_ID'] for t in logainm_data['townlands'] if t['CP_OSM_ID'] == civil_parish_id and t['BAR_OSM_ID'] != '' )

def parent_osmid_for_obj_osmid(logainm_data, obj_osmid, obj_key, parent_key):
    result = logainm_data['index'][obj_key][parent_key][obj_osmid]
    return result

def baronies_matchup(logainm_data, cursor, existing_match_ups):
    return hierachial_matchup(logainm_data, cursor,
                key='baronies', obj_logainm_code="BAR", parent_logainm_code='CON',
                obj_key="BAR_OSM_ID", parent_key="CO_OSM_ID", parent_name="county",
                existing_match_ups=existing_match_ups,
         )

def civil_parish_matchup(logainm_data, cursor, existing_match_ups):
    return hierachial_matchup(logainm_data, cursor,
                key='civil_parishes', obj_logainm_code="PAR", parent_logainm_code='BAR',
                obj_key="CP_OSM_ID", parent_key="BAR_OSM_ID", parent_name="barony",
                existing_match_ups=existing_match_ups,
         )

def townlands_matchup(logainm_data, cursor, existing_match_ups):
    return hierachial_matchup(logainm_data, cursor,
                key='townlands', obj_logainm_code="BF", parent_logainm_code='PAR',
                obj_key="OSM_ID", parent_key="CP_OSM_ID", parent_name="civil parish",
                existing_match_ups=existing_match_ups,
         )

def hierachial_matchup(logainm_data, cursor, key, obj_logainm_code, parent_logainm_code, obj_key, parent_key, parent_name, existing_match_ups=None):
    existing_match_ups = existing_match_ups or {}
    logger.info("Have %d %s in total", len(logainm_data[key]), key)
    results = {}

    possibles = [b for b in logainm_data[key] if b['LOGAINM_RE'] == '']
    logger.info("Found %(len)d (%(percent)f%%) %(type)s without logainm ref", dict(len=len(possibles), type=key, percent=(len(possibles)*100/len(logainm_data[key]))))

    for obj in possibles:
        logger.debug("Starting to look at %s %s (osm:%s)", key, name_en(obj), obj['OSM_ID'])
        parent_osm_id = parent_osmid_for_obj_osmid(logainm_data, obj['OSM_ID'], obj_key, parent_key)
        if len(parent_osm_id) == 0:
            logger.error("ERROR No %s found for %s %s (%s) in OSM: Tie: http://www.townlands.ie/by/osm_id/%s", parent_name, key, name_en(obj), obj['OSM_ID'], obj['OSM_ID'])
            continue
        elif len(parent_osm_id) > 1:
            logger.error("ERROR Found %s (%s) %s for %s %s (osmid=%s) in OSM", len(parent_osm_id), ",".join(parent_osm_id), parent_name, key, name_en(obj), obj['OSM_ID'])
            continue
        elif len(parent_osm_id) == 1:
            parent_osm_id = parent_osm_id.pop()
            try:
                parent_logainm_id = osmid_to_logainm_ref(logainm_data, parent_osm_id, existing_match_ups)
                if ";" in parent_logainm_id:
                    logger.error("ERROR %s %s (%s) is in %s %s in OSM which is many logainms: %s Tie: http://www.townlands.ie/by/osm_id/%s", key, name_en(obj), obj['OSM_ID'], parent_name, parent_osm_id, parent_logainm_id, obj['OSM_ID'])
                    continue
                else:
                    logger.debug("OK %s %s (%s) is in %s %s in OSM which is logainm id %s", key, name_en(obj), obj['OSM_ID'], parent_name, parent_osm_id, parent_logainm_id)
            except (IndexError, KeyError):
                logger.error("ERROR %s %s (%s) is in %s %s in OSM which has no known logainm", key, name_en(obj), obj['OSM_ID'], parent_name, parent_osm_id)
                continue
        else:
            assert False

        # Now we have the logainm ref of the parent that this obj is in.
        # Look at the logainm data for the objs in that bar
        cursor.execute("select obj.logainm_id from names as parent join geometric_contains as con on (parent.logainm_id = con.outer_obj_id) join names as obj on (obj.logainm_id = con.inner_obj_id) where parent.logainm_category_code = ? and obj.logainm_category_code = ? and parent.logainm_id = ? and obj.name_en = ?;", [parent_logainm_code, obj_logainm_code, parent_logainm_id, name_en(obj)])
        data = cursor.fetchall()
        data_str = ", ".join(x[0] for x in data)
        if len(data) == 0:
            logger.error("ERROR %s %s (%s) is in %s OSM:%s (logainm:%s) http://www.townlands.ie/by/osm_id/%s/ which has no %s in logainm for this name", key, name_en(obj), obj['OSM_ID'], parent_name, parent_osm_id, parent_logainm_id, obj['OSM_ID'], key)
            continue
        elif len(data) > 1:
            logger.error("ERROR %s %s (%s) is in %s OSM:%s (logainm:%s) has >1 %s in logainm for this name: %s", key, name_en(obj), obj['OSM_ID'], parent_name, parent_osm_id, parent_logainm_id, key, data_str)
            continue
        elif len(data) == 1:
            logger.info("OK %s %s (%s) is in %s OSM:%s (logainm:%s) has 1 %s in logainm for this name: %s", key, name_en(obj), obj['OSM_ID'], parent_name, parent_osm_id, parent_logainm_id, data_str, key)
            # remove leading '-' character
            results[('relation', obj['OSM_ID'][1:])] = get_logainm_tags(cursor, data[0][0])
        else:
            assert False


    logger.info("Matched up %d %s of %d without a logainm id (%s%%)", len(results), key, len(possibles), (len(results)*100)/len(possibles))
    return results

def remove_and_warn_dupes(logainm_candidates):
    logainm_ref_to_osm = defaultdict(set)
    for key, tags in logainm_candidates.items():
        logainm_ref = tags['logainm_id']
        logainm_ref_to_osm[logainm_ref].add(key)

    for logainm_ref in logainm_ref_to_osm:
        osms = logainm_ref_to_osm[logainm_ref]
        if len(osms) > 1:
            logger.error("ERROR Duplicates - %s has been matched to the following OSM ids: %s", logainm_ref, ", ".join("{} {}".format(*x) for x in osms))
            for key in osms:
                del logainm_candidates[key]

    return logainm_candidates

def limit(logainm_candidates, limit):
    if limit is None:
        return logainm_candidates

    limit = int(limit)
    logainm_candidates = dict((sorted(logainm_candidates.items()))[:limit])

    return logainm_candidates

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input")
    parser.add_argument("-o", "--output")
    parser.add_argument("--baronies", action="store_true")
    parser.add_argument("--civil-parishes", action="store_true")
    parser.add_argument("--townlands", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-n", "--dry-run", action="store_true")

    parser.add_argument("-l", "--limit")

    args = parser.parse_args()

    ch = logging.StreamHandler(sys.stdout)
    if args.verbose:
        ch.setLevel(logging.DEBUG)
    else:
        ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s\t%(levelname)s\tL%(lineno)s\t%(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    conn = sqlite3.connect("logainm.sqlite")
    cursor = conn.cursor()

    logger.setLevel(logging.DEBUG)

    logainm_data = read_logainm_data()

    logainm_candidates = {}

    if args.baronies:
        logainm_candidates.update(baronies_matchup(logainm_data, cursor, logainm_candidates))

    if args.civil_parishes:
        logainm_candidates.update(civil_parish_matchup(logainm_data, cursor, logainm_candidates))

    if args.townlands:
        logainm_candidates.update(townlands_matchup(logainm_data, cursor, logainm_candidates))

    logainm_candidates = remove_and_warn_dupes(logainm_candidates)
    logainm_candidates = limit(logainm_candidates, args.limit)

    if args.dry_run:
        return

    # read in OSM XML
    with printer("reading in OSM XML"):
        tree = ET.parse(args.input)
        root = tree.getroot()

    # add new tags to OSM XML
    with printer("adding XML tags"):
        for rel in root.findall("relation"):
            osm_id = rel.get("id", None)
            if ('relation', osm_id) in logainm_candidates:

                # This tag is needed so JOSM knows to upload it
                rel.set("action", "modify")

                logging.debug("Adding tags to OSM_ID %d", osm_id)
                logaimn_data = logainm_candidates[('relation', osm_id)]
                for k, v in logainm_tags(rel, logaimn_data).items():
                    ET.SubElement(rel, 'tag', {'k': k, 'v': v})
            else:
                root.remove(rel)


    # write out OSM XML
    tree.write(args.output, encoding='utf-8', xml_declaration=True) 

if __name__ == '__main__':
    main()


