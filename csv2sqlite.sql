.separator ","
.import ./logainm-csvs/logainm_names.csv names
.import ./logainm-csvs/geometric_contains.csv geometric_contains
.import ./logainm-csvs/geometries.csv geometries
.import ./logainm-csvs/logainm_categories.csv categories
create view name_contains as select outer.logainm_id as outer_logainm_id, outer.logainm_category_code as outer_logainm_category_code, outer.name_en as outer_name_en, outer.name_ga as outer_name_ga, inner.logainm_id as inner_logainm_id, inner.logainm_category_code as inner_logainm_category_code, inner.name_en as inner_name_en, inner.name_ga as inner_name_ga from names as outer join geometric_contains as c on (outer.logainm_id = c.outer_obj_id) join names as inner on (inner.logainm_id = c.inner_obj_id);
