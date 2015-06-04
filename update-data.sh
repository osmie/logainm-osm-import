#! /bin/bash

set -o errexit

wget -nc http://www.technomancy.org/logainm/logainm-csvs.zip
rm -rf logainm-csvs || true
aunpack logainm-csvs.zip
wget -O ireland-and-northern-ireland.osm.pbf http://planet.openstreetmap.ie/ireland-and-northern-ireland.osm.pbf
./create-xml-files.sh
for TYPE in townlands eds civil_parishes baronies counties ; do
    wget -O ${TYPE}.zip http://www.townlands.ie/static/downloads/${TYPE}.zip
    rm -rf ${TYPE} || true
    aunpack ${TYPE}.zip
done
