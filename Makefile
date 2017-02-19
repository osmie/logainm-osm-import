SHELL := bash

redo: redownload new-boundaries.osm.xml

redownload: rmosmdata boundaries.osm.xml townlands-no-geom.csv baronies-no-geom.csv civil_parishes-no-geom.csv counties-no-geom.csv

all: boundaries.osm.xml townlands-no-geom.csv baronies-no-geom.csv civil_parishes-no-geom.csv counties-no-geom.csv

rmosmdata:
	-rm boundaries.osm.xml new-boundaries.osm.xml
	-rm *-no-geom.csv*
	-rm ireland-and-northern-ireland.osm.pbf

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
	xmlstarlet c14n boundaries.osm.xml > boundaries2.osm.xml
	mv boundaries2.osm.xml boundaries.osm.xml

new-boundaries.osm.xml: boundaries.osm.xml logainm.sqlite match.py townlands-no-geom.csv \
	baronies-no-geom.csv civil_parishes-no-geom.csv counties-no-geom.csv
	mkdir -p ./output/`date -I`
	python match.py --verbose --input boundaries.osm.xml --output new-boundaries.osm.xml --baronies --civil-parishes --townlands | tee >( lzma > ./output/`date -I`/output.lzma)
	xmlstarlet c14n new-boundaries.osm.xml > new-boundaries2.osm.xml
	mv new-boundaries2.osm.xml new-boundaries.osm.xml

bar-dry-run: boundaries.osm.xml logainm.sqlite match.py townlands-no-geom.csv \
	baronies-no-geom.csv civil_parishes-no-geom.csv counties-no-geom.csv
	python match.py --verbose --input boundaries.osm.xml --output new-boundaries.osm.xml --baronies --dry-run

cp-dry-run: boundaries.osm.xml logainm.sqlite match.py townlands-no-geom.csv \
	baronies-no-geom.csv civil_parishes-no-geom.csv counties-no-geom.csv
	python match.py --verbose --input boundaries.osm.xml --output new-boundaries.osm.xml --baronies --civil-parishes --dry-run

td-dry-run: boundaries.osm.xml logainm.sqlite match.py townlands-no-geom.csv \
	baronies-no-geom.csv civil_parishes-no-geom.csv counties-no-geom.csv
	python match.py --verbose --input boundaries.osm.xml --output new-boundaries.osm.xml --baronies --civil-parishes --townlands --dry-run

sample: clean new-boundaries.osm.xml boundaries.osm.xml
	tar -cf sample-data-`date -I`.tar boundaries.osm.xml new-boundaries.osm.xml
	lzma sample-data-`date -I`.tar

lint: boundaries.osm.xml
	python logainm_lint.py -i boundaries.osm.xml --dupe-logainm-ref

add_all_tags: boundaries.osm.xml
	python add_all_logainm_tags.py -i boundaries.osm.xml -o boundaries-all-logainm-tags.osm.xml

