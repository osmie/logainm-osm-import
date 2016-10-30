"""
Initial import(s) had some bad names where some letters with fada instead had
"??". The souce logainm data was fixed, and this script will fix the osm
objects which have this bd data
"""
import sys
import logging
from contextlib import contextmanager
import csv
import sqlite3
import xml.etree.ElementTree as ET
import argparse
from collections import defaultdict
import re

logging.getLogger().setLevel(logging.DEBUG)
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input")
    parser.add_argument("-o", "--output")
    parser.add_argument("-n", "--dry-run", action="store_true")

    args = parser.parse_args()

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s\t%(levelname)s\tL%(lineno)s\t%(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    conn = sqlite3.connect("logainm.sqlite")
    cursor = conn.cursor()

    # read in OSM XML
    with printer("reading in OSM XML"):
        tree = ET.parse(args.input)
        root = tree.getroot()

    # add new tags to OSM XML
    with printer("correcting names"):
        for rel in root.findall("relation"):
            osm_id = rel.get("id", None)
            tags = get_existing_osm_tags(rel)
            has_been_changed = False
            
            for name_ga in ['name:ga', 'official_name:ga']:
                if '??' in tags.get(name_ga, "") and 'logainm:ref' in tags:
                    bad_name = tags[name_ga]
                    try:
                        logainmref = int(tags['logainm:ref'])
                    except:
                        # can't int. probably semi-colon multiple
                        continue

                    cursor.execute("select name_ga from names where logainm_id = ?", [logainmref])
                    correct_name = cursor.fetchone()[0]
                    if correct_name is None:
                        logger.debug("No name_ga for logainm_id %s", logainmref)
                        continue

                    if bad_name == correct_name:
                        continue

                    logger.info("Have encoding problem for osmid %(osmid)s, Current %(k)s=%(v)s logainm:ref=%(logainmref)s correct name = %(correct)s",
                                 {'osmid': osm_id, 'k': name_ga, 'v': bad_name, 'logainmref': tags['logainm:ref'], 'correct': correct_name})

                    # change the tag
                    rel.set("action", "modify")
                    has_been_changed = True

                    for tag in rel.findall("tag"):
                        if tag.attrib["k"] == name_ga:
                            tag.set("v", correct_name)

            if not has_been_changed:
                root.remove(rel)


    # write out OSM XML
    with printer("writing out OSM XML"):
        tree.write(args.output, encoding='utf-8', xml_declaration=True) 

if __name__ == '__main__':
    main()


