#! /bin/bash

rm -f logainm.sqlite || true
cat csv2sqlite.sql | sqlite3 logainm.sqlite
