"""
Add the correct logainm tags to all objects
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


def set_tag(osmobj, k, v):
    if v is None:
        return

    updated_existing_tag = False
    for tag in osmobj.findall("tag"):
        if tag.attrib["k"] == k:
            tag.set("v", v)
            updated_existing_tag = True

    if not updated_existing_tag:
        ET.SubElement(osmobj, 'tag', {'k': k, 'v': v})

def set_if_missing(osmobj, k, v):
    if v is None:
        # Do nothing for empty values
        return

    existing_value = [tag.attrib['v'] for tag in osmobj.findall("tag") if tag.attrib.get("k") == k]
    existing_value = existing_value[0] if len(existing_value) > 0 else None
    if existing_value is None:
        logger.debug("Settting %(k)s=%(v)s for osmobj %(id)s", {'k': k, 'v': v, 'id': osmobj.attrib['id']})
        set_tag(osmobj, k, v)
    elif existing_value != v:
        logger.debug("relation %(id)s tag %(k)s is %(current)r. Wanted to set to %(new)r", {'id':osmobj.attrib['id'], 'k': k, 'current': existing_value, 'new': v})
    else:
        # it has a value, which is the same as what we want to set, so just skip
        pass
            

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
            
            if 'logainm:ref' in tags:
                try:
                    logainmref = int(tags['logainm:ref'])
                except:
                    # can't int. probably semi-colon multiple
                    continue

                cursor.execute("select * from names where logainm_id = ?", [logainmref])
                logainm_data = cursor.fetchone()
                if logainm_data is None:
                    logger.debug("No logainm data for logainm_id %s", logainmref)
                    continue
                logainm_data = {k: logainm_data[i] for i, k in enumerate([
                        "logainm_id", "logainm_category_code", "logainm_permalink", "placenamesni_link",
                        "name_en", "name_ga", "name_ga_genitive", ])
                }

                if 'logainm:url' not in tags or tags['logainm:url'] == 'http://www.logainm.ie/en/{}'.format(logainm_data['logainm_id']):
                    logger.debug("Setting logainm:url to %(url)s for osm id %(id)s", {'url': logainm_data['logainm_permalink'], 'id': logainm_data['logainm_id']})
                    set_tag(rel, 'logainm:url', logainm_data.get("logainm_permalink"))

                set_if_missing(rel, "name:ga", logainm_data.get("name_ga"))
                set_if_missing(rel, "name:en", logainm_data.get("name_en"))

                if logainm_data.get('placenamesni_link'):
                    link = logainm_data['placenamesni_link']
                    set_if_missing(rel, "placenamesni:url", link)
                    match = re.match("^http://www\.placenamesni\.org/resultdetails\.php\?entry=([0-9]+)$", link)
                    if match:
                        pnni_id = match.groups()[0]
                        set_if_missing(rel, "placenamesni:ref", pnni_id)


                # change the tag
                rel.set("action", "modify")
                has_been_changed = True


            if not has_been_changed:
                root.remove(rel)


    # write out OSM XML
    with printer("writing out OSM XML"):
        tree.write(args.output, encoding='utf-8', xml_declaration=True) 

if __name__ == '__main__':
    main()


