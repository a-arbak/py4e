When exporting the EPS from OmniGraffle

* Change the Export Area to "All Objects"
* Set the margin to 0 (no margin)

To make PNGs from EPS

* Go into ../images
* Open the eps with TexShop (assuming it is installed)
* TexShop will autovconvert and save as PDF
* Open PDF in preview and export as PNG - set DPI to 300
* Delete the PDF

Sadly, OmniGraffle's Export to PNG leaves an asymetric black border
and makes things look bad.

Turkish translation
-------------------

In this fork the figures in ../images are translated to Turkish, but the
.graffle files here are still the English originals (OmniGraffle is not
available to the translators). The Turkish SVG, EPS and PNG files are
generated from the English SVGs by ../tr/figures.py using the strings in
../tr/figures.json:

    python tr/figures.py arch pda --out images

Edit tr/figures.json and rerun the script instead of editing the images
by hand.
