"""
Perform some linting on the logainm data that's currently in OSM
"""
import sys
import argparse
import logging
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from collections import defaultdict

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


def duplicate_logainm_refs(osm_xml_root):
    logainm_ref_to_osm_id = defaultdict(set)
    for rel in osm_xml_root.iter("relation"):
        osm_id = rel.get("id", None)
        tags = get_existing_osm_tags(rel)
        if 'logainm:ref' in tags:
            logainm_ref_to_osm_id[tags['logainm:ref']].add(osm_id)

    num_dupe_refs = 0
    num_osm_dupes = 0
    for lref, osms in logainm_ref_to_osm_id.items():
        if len(osms) > 1:
            logger.info("logainm:ref={} for these {} OSM relations: {}".format(lref, len(osms), ", ".join(osms)))
            logger.info("View on logainm: http://logainm.ie/en/{}".format(lref))
            for osmid in osms:
                logger.info("View on OSM: http://www.openstreetmap.org/relation/{}".format(osmid))
            num_dupe_refs += 1
            num_osm_dupes += len(osms)

    logger.info("There are {} duplicate logainm:refs which affect {} OSM objects".format(num_dupe_refs, num_osm_dupes))



def main(args=None):
    args = args or sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True)
    parser.add_argument("-v", "--verbose", action="store_true")

    parser.add_argument("--dupe-logainm-ref", action="store_true")

    args = parser.parse_args(args)

    ch = logging.StreamHandler(sys.stdout)
    if args.verbose:
        ch.setLevel(logging.DEBUG)
    else:
        ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s\t%(levelname)s\tL%(lineno)s\t%(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)

    logger.info("Starting")

    # read in OSM XML
    with printer("reading in OSM XML"):
        tree = ET.parse(args.input)
        root = tree.getroot()

    if args.dupe_logainm_ref:
        duplicate_logainm_refs(root)
    


if __name__ == '__main__':
    main(sys.argv[1:])
