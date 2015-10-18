#! /usr/bin/python
# encoding: utf-8
import sqlite3
import pprint
from jinja2 import Template

logainm = {}

conn = sqlite3.connect("../logainm.sqlite")
cursor = conn.cursor()

cursor.execute("select logainm_id, name_en, name_ga from names where logainm_category_code = 'CON'")
logainm['counties'] = []
for c in list(cursor.fetchall()):
    baronies = []
    logainm['counties'].append({
        'id': c[0],
        'name_en': c[1],
        'name_ga': c[2],
        'baronies': baronies,
    })

    cursor.execute("select logainm_id, name_en, name_ga from names join geometric_contains where names.logainm_category_code = 'BAR' and geometric_contains.inner_obj_id = names.logainm_id and geometric_contains.outer_obj_id = ?", [c[0]])
    for barony in list(cursor.fetchall()):
        cps = []
        baronies.append({
            'id': barony[0],
            'name_en': barony[1],
            'name_ga': barony[2],
            'civil_parishes': cps
        })

        cursor.execute("select logainm_id, name_en, name_ga from names join geometric_contains where names.logainm_category_code = 'PAR' and geometric_contains.inner_obj_id = names.logainm_id and geometric_contains.outer_obj_id = ?", [barony[0]])
        for cp in list(cursor.fetchall()):
            townlands = []
            cps.append({
                'id': cp[0],
                'name_en': cp[1],
                'name_ga': cp[2],
                'townlands': townlands,
            })

            cursor.execute("select logainm_id, name_en, name_ga from names join geometric_contains where names.logainm_category_code = 'BF' and geometric_contains.inner_obj_id = names.logainm_id and geometric_contains.outer_obj_id = ?", [cp[0]])
            for t in list(cursor.fetchall()):
                townlands.append({
                    'id': t[0],
                    'name_en': t[1],
                    'name_ga': t[2],
                })



all_template_src = u"""<!DOCTYPE html><html>
<head>
    <meta charset="utf-8">
    <link href="/static/bootstrap/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
<div class="container">
<h1>Logainm data</h1>
<p>This page shows the <a href="http://www.logainm.ie">Logainm</a> data in a format for adding to <a href="http://www.openstreetmap.org">OpenStreetMap</a> with the <a href="http://level0.osmz.ru/">Level0</a> editor.</p>
<p>Many of this counties/baronies/etc are not yet in OSM, and hence the "Check on Townlands.ie" will not work.</p>
<p>The <code>logainm:ref</code> tag should be added to all the objects. I've suggested <code>official_name:en</code> and <code>official_name:ga</code>, but for objects in Northern Ireland this is not correct, and so those tags should not be added there unless you know it's accurate.</p>
<p>The Irish names are mostly accurate, but sometimes there is an encoding problem with letters with fadas. Don't copy the wrong value from here, check what the proper Irish name is on Logainm and use that.</p>
<ul>
    {% for county in counties|sort(attribute='name_en') %}
        <li><a href="#county{{ county.id }}">{{ county.name_en }}</a>
    {% endfor %}
</ul>
<p>
<a href="/">Back to Townlands.ie</a>
</p>
{% for county in counties|sort(attribute='name_en') %}
    <h2 id="county{{ county.id }}">County: {{ county.name_en }}</h2>
        <p><a href="http://www.townlands.ie/by/logainm/{{ county.id }}">Search Townlands.ie by logainm ref</a> - <a href="http://www.townlands.ie/search/?q={{ county.name_en }}">Search Townlands.ie by name</a> - <a href="http://www.logainm.ie/en/{{ county.id }}">View on Logaimn</a></p>
        <p><a href="counties/{{ county.name_en }}.html">View Townlands in {{ county.name_en }}</a></p>
<textarea id=text readonly rows=3 cols=80>
  logainm:ref = {{ county.id }}
  official_name:en = {{ county.name_en }}{% if county.name_ga %}
  official_name:ga = {{ county.name_ga }}{% endif %}
</textarea>
    <div class="small">
    <ul class="list-unstyled">
        {% for barony in county.baronies|sort(attribute='name_en') %}
        <li>
            <a href="#barony{{ barony.id }}">{{ barony.name_en }}</a>
            <ul class="list-inline small">
                {% for cp in barony.civil_parishes|sort(attribute='name_en') %}
                <li>
                    <a href="#cp{{ cp.id }}">{{ cp.name_en }}</a>
                </li>
                {% endfor %}
            </ul>
        </li>
        {% endfor %}
    </ul>
    </div>

    {% for barony in county.baronies|sort(attribute='name_en') %}
        <h3 id="barony{{barony.id }}">Barony: {{ barony.name_en }}</h3>
            <a href="#county{{ county.id }}">Co. {{ county.name_en }}</a> → <b>Barony {{ barony.name_en }}</b>
            <p><a href="http://www.townlands.ie/by/logainm/{{ barony.id }}">Search Townlands.ie by logainm ref</a> - <a href="http://www.townlands.ie/search/?q={{ barony.name_en }}">Search Townlands.ie by name</a> - <a href="http://www.logainm.ie/en/{{ barony.id }}">View on Logaimn</a></p>
<textarea readonly rows=3 cols=80>
  logainm:ref = {{ barony.id }}
  official_name:en = {{ barony.name_en }}{% if barony.name_ga %}
  official_name:ga = {{ barony.name_ga }}{% endif %}
</textarea>
        {% for cp in barony.civil_parishes|sort(attribute='name_en') %}
            <h4 id="cp{{ cp.id }}">Civil Parish: {{ cp.name_en }}</h4>
                <a href="#county{{ county.id }}">Co. {{ county.name_en }}</a> → <a href="#barony{{ barony.id }}">Barony {{ barony.name_en }}</a> → <b>Civil Parish {{ cp.name_en }}</b>
                <p><a href="http://www.townlands.ie/by/logainm/{{ cp.id }}">Search Townlands.ie by logainm ref</a> - <a href="http://www.townlands.ie/search/?q={{ cp.name_en }}">Search Townlands.ie by name</a> - <a href="http://www.logainm.ie/en/{{ cp.id }}">View on Logaimn</a></p>
<textarea readonly rows=3 cols=80>
  logainm:ref = {{ cp.id }}
  official_name:en = {{ cp.name_en }}{% if cp.name_ga %}
  official_name:ga = {{ cp.name_ga }}{% endif %}
</textarea>
        {% endfor %}
    {% endfor %}
{% endfor %}
</div>
</body>

</html>
"""

all_template = Template(all_template_src)
with open("index.html" ,'w') as fp:
    fp.write(all_template.render(counties=logainm['counties']).encode("utf-8"))


per_county_template_src = u"""<!DOCTYPE html><html>
<head>
<meta charset="utf-8">
</head>
<body>
<h1>Logainm data for {{ county.name_en }}</h1>
<p><a href="..">All counties></a></p>
{% for barony in county.baronies|sort(attribute='name_en') %}
    <h2>Barony: {{ barony.name_en }}</h3>
    Co. {{ county.name_en }} → Barony {{ barony.name_en }}
    <p><a href="http://www.townlands.ie/by/logainm/{{ barony.id }}">Search Townlands.ie by logainm ref</a> - <a href="http://www.townlands.ie/search/?q={{ barony.name_en }}">Search Townlands.ie by name</a> - <a href="http://www.logainm.ie/en/{{ barony.id }}">View on Logaimn</a></p>
    {% for cp in barony.civil_parishes|sort(attribute='name_en') %}
        <h2>Civil Parish: {{ cp.name_en }}</h4>
        Co. {{ county.name_en }} → Barony {{ barony.name_en }} → Civil Parish {{ cp.name_en }}
        <p><a href="http://www.townlands.ie/by/logainm/{{ cp.id }}">Search Townlands.ie by logainm ref</a> - <a href="http://www.townlands.ie/search/?q={{ cp.name_en }}">Search Townlands.ie by name</a> - <a href="http://www.logainm.ie/en/{{ cp.id }}">View on Logaimn</a></p>
        {% for td in cp.townlands|sort(attribute='name_en') %}
            <h3>Townland: {{ td.name_en }}</h4>
                Co. {{ county.name_en }} → Barony {{ barony.name_en }} → Civil Parish {{ cp.name_en }} → Townland {{ td.name_en }}
                <p><a href="http://www.townlands.ie/by/logainm/{{ td.id }}">Search Townlands.ie by logainm ref</a> - <a href="http://www.townlands.ie/search/?q={{ td.name_en }}">Search Townlands.ie by name</a> - <a href="http://www.logainm.ie/en/{{ td.id }}">View on Logaimn</a></p>
<textarea readonly rows=3 cols=80>
  logainm:ref = {{ td.id }}
  official_name:en = {{ td.name_en }}{% if td.name_ga %}
  official_name:ga = {{ td.name_ga }}{% endif %}
</textarea>
        {% endfor %}
    {% endfor %}
{% endfor %}
</body>

</html>
"""

per_county_template = Template(per_county_template_src)
for county in logainm['counties']:
    with open("counties/"+county['name_en']+".html", "w") as fp:
        fp.write(per_county_template.render(county=county).encode("utf-8"))
