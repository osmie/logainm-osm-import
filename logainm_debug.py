import sys
import logging
import csv
import sqlite3
import argparse

reload(sys)
sys.setdefaultencoding('utf-8')


def main():

    parser = argparse.ArgumentParser()
    #parser.add_argument("mbtilesfilename")
    parser.add_argument("logainm_id")

    args = parser.parse_args()
    logainm_id = args.logainm_id

    conn = sqlite3.connect("logainm.sqlite")
    cursor = conn.cursor()

    cursor.execute("select names.name_en, names.name_ga, cat.name_en from names join categories as cat on (names.logainm_category_code = cat.logainm_category_code) where logainm_id = ?", [logainm_id])
    data = cursor.fetchone()
    if len(data) == 0:
        print "Logainm id {} not found".format(logainm_id)
        return

    name_en, name_ga, category = data
    print u"Logainm [{}] {} {}/{}".format(category, logainm_id, name_en, name_ga)

    cursor.execute("select inner_obj_id, names.name_en, names.name_ga, cat.name_en from geometric_contains as c join names on (c.inner_obj_id = names.logainm_id) join categories as cat ON (cat.logainm_category_code = names.logainm_category_code) where c.outer_obj_id = ? ORDER BY cat.name_en", [logainm_id])
    children_logainm_id = cursor.fetchall()
    
    print "Children objects:"
    if len(children_logainm_id) == 0:
        print " No children"
    else:
        for c in children_logainm_id:
            print u" * [{3}] {1}/{2} ({0} http://www.logainm.ie/en/{0})".format(*c)

    cursor.execute("select outer_obj_id, names.name_en, names.name_ga, cat.name_en from geometric_contains as c join names on (c.inner_obj_id = names.logainm_id) join categories as cat ON (cat.logainm_category_code = names.logainm_category_code) where c.inner_obj_id = ? ORDER BY cat.name_en", [logainm_id])
    parents = cursor.fetchall()
    
    print "Parent objects:"
    if len(parents) == 0:
        print " No parents"
    else:
        for c in parents:
            print u" * [{3}] {1}/{2} ({0} http://www.logainm.ie/en/{0})".format(*c)





if __name__ == '__main__':
    main()


