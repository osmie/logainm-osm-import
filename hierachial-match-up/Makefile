SHELL := bash

all: boundaries.osm.xml

clean:
	-rm boundaries.osm.xml
	-rm -f {townlands,civil_parishes,baronies}-no-geom.csv
	-rm ireland-and-northern-ireland.osm.pbf

ireland-and-northern-ireland.osm.pbf:
	wget -O ireland-and-northern-ireland.osm.pbf http://planet.openstreetmap.ie/ireland-and-northern-ireland.osm.pbf

%-no-geom.csv.zip:
	wget http://www.townlands.ie/static/downloads/$@

%-no-geom.csv: %-no-geom.csv.zip
	-rm -f $@
	aunpack $<

boundaries.osm.xml: ireland-and-northern-ireland.osm.pbf
	osmosis --read-pbf ireland-and-northern-ireland.osm.pbf --tag-filter reject-way --tag-filter reject-node --tag-filter accept-relations admin_level=* outPipe.0=admin_level --read-pbf ireland-and-northern-ireland.osm.pbf --tag-filter reject-way --tag-filter reject-node --tag-filter accept-relations boundary=* outPipe.0=boundaries --merge inPipe.0=admin_level inPipe.1=boundaries --write-xml boundaries.osm.xml
