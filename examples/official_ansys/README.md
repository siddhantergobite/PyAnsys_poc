# Archived official PyMAPDL example sources

These files are unmodified, MIT-licensed downloads from the official PyMAPDL
stable documentation. They are retained for provenance and review. The API does
not execute them directly because each source launches and exits its own MAPDL
process and uses fixed tutorial parameters.

The parameterized application adaptations are implemented in
`app/simulation/official_examples.py` and retain the documented element
formulations and model approach:

- `bracket_static.py`: PLANE183 plane-stress corner bracket.
- `2d_plate_with_a_hole.py`: PLANE183 plane-stress plate with a central hole.
- `2d_pressure_vessel.py`: PLANE182 plane-strain quarter pressure vessel.

Downloaded from:

- https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/bracket_static.html
- https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/2d_plate_with_a_hole.html
- https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/2d_pressure_vessel.html

The element implementations PLANE183 and PLANE182 are built into MAPDL. They
are selected by the `ET` command; they are not external model files.
