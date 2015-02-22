#! /bin/bash

osmosis --read-pbf ireland-and-northern-ireland.osm.pbf --lp --tag-filter reject-way --tag-filter reject-node --tag-filter accept-relations admin_level=10 --write-xml townlands.osm.xml
