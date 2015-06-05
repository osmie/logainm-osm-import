#! /bin/bash

osmosis --read-pbf ireland-and-northern-ireland.osm.pbf --tag-filter reject-way --tag-filter reject-node --tag-filter accept-relations admin_level=* outPipe.0=admin_level --read-pbf ireland-and-northern-ireland.osm.pbf --tag-filter reject-way --tag-filter reject-node --tag-filter accept-relations boundary=* outPipe.0=boundaries --merge inPipe.0=admin_level inPipe.1=boundaries --write-xml boundaries.osm.xml
