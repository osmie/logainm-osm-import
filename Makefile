SHELL := bash

all: boundaries.osm.xml townlands-no-geom.csv baronies-no-geom.csv civil_parishes-no-geom.csv counties-no-geom.csv

clean:
	git clean -x -f

ireland-and-northern-ireland.osm.pbf:
	wget -O ireland-and-northern-ireland.osm.pbf http://planet.openstreetmap.ie/ireland-and-northern-ireland.osm.pbf

%-no-geom.csv.zip:
	wget http://www.townlands.ie/static/downloads/$@

%-no-geom.csv: %-no-geom.csv.zip
	-rm -f $@
	aunpack $<

boundaries.osm.xml: ireland-and-northern-ireland.osm.pbf
	osmosis --read-pbf ireland-and-northern-ireland.osm.pbf --tag-filter reject-way --tag-filter reject-node --tag-filter accept-relations admin_level=* outPipe.0=admin_level --read-pbf ireland-and-northern-ireland.osm.pbf --tag-filter reject-way --tag-filter reject-node --tag-filter accept-relations boundary=* outPipe.0=boundaries --merge inPipe.0=admin_level inPipe.1=boundaries --write-xml boundaries.osm.xml
	xmlstarlet c14n boundaries.osm.xml | sponge boundaries.osm.xml

new-boundaries.osm.xml: boundaries.osm.xml logainm.sqlite match.py townlands-no-geom.csv \
	baronies-no-geom.csv civil_parishes-no-geom.csv counties-no-geom.csv
	python match.py --verbose --input boundaries.osm.xml --output new-boundaries.osm.xml --baronies --civil-parishes --townlands
	xmlstarlet c14n new-boundaries.osm.xml | sponge new-boundaries.osm.xml

sample: clean new-boundaries.osm.xml boundaries.osm.xml
	tar -cf sample-data-`date -I`.tar boundaries.osm.xml new-boundaries.osm.xml
	lzma sample-data-`date -I`.tar

logainm-csvs.zip:
	wget -O logainm-csvs.zip http://www.technomancy.org/logainm/logainm-csvs.zip

logainm-csvs/logainm_names.csv: logainm-csvs.zip
	aunpack logainm-csvs.zip
	# Without this, the datetime in logainm_name.csvs will be old and hence
	# it'll always try to rename thistarget
	touch logainm-csvs/*

logainm.sqlite: logainm-csvs/logainm_names.csv
	-rm -f logainm.sqlite
	cat csv2sqlite.sql | sqlite3 logainm.sqlite

lint: boundaries.osm.xml
	python logainm_lint.py -i boundaries.osm.xml --dupe-logainm-ref
