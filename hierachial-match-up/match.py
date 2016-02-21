import csv

@contextmanager
def printer(msg):
    msg = msg.strip()
    logger.info("Started "+msg)
    yield
    logger.info("Finished "+msg)


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
            #('townlands/townlands.shp', 'townland'),
                    ('counties/counties.shp', 'county'),
                    ('baronies/baronies.shp', 'barony'),
            #('civil_parishes/civil_parishes.shp', 'civil_parish'),
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

    logainm_candidates = {}


    cursor.execute("select 'County '||name_en, logainm_id from names where logainm_category_code = 'CON' and name_en = 'Carlow';")
    logainm_counties = dict(cursor.fetchall())

    for county_name in logainm_counties:
        logger.info("Dealing with %s", county_name)
        osm_county = [b for b in boundaries if b['type'] == 'county' and 'County '+b['properties']['NAME'] == county_name][0]
        logainm_data = get_logainm_tags(cursor, logainm_counties[county_name])
        logainm_candidates[('relation', str(abs(int(osm_county['properties']['OSM_ID']))))] = logainm_data

        logainm_baronies = []
        cursor.execute("select name_en, logainm_id from names where logainm_category_code = 'BAR';")


    print logainm_candidates
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

if __name__ == '__main__':
    main()


