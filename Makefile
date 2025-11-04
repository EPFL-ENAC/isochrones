install:
	uv pip install -e .

test:
	uv run pytest -s

install-tools:
	sudo apt install -y osmium-tool josm

pbf: pbf-download pbf-merge

pbf-download:
	@rm -rf data/geofabrik
	@mkdir -p data/geofabrik
	wget https://download.geofabrik.de/europe/switzerland-latest.osm.pbf -O data/geofabrik/switzerland-latest.osm.pbf
	wget https://download.geofabrik.de/europe/france/rhone-alpes-latest.osm.pbf -O data/geofabrik/rhone-alpes-latest.osm.pbf
	wget https://download.geofabrik.de/europe/france/franche-comte-latest.osm.pbf -O data/geofabrik/franche-comte-latest.osm.pbf
	wget https://download.geofabrik.de/europe/france/alsace-latest.osm.pbf -O data/geofabrik/alsace-latest.osm.pbf
	wget https://download.geofabrik.de/europe/france/bourgogne-latest.osm.pbf -O data/geofabrik/bourgogne-latest.osm.pbf
	wget https://download.geofabrik.de/europe/italy/nord-ovest-latest.osm.pbf -O data/geofabrik/italy-nord-ovest-latest.osm.pbf

pbf-merge:
	@rm -f data/merged.osm.pbf
	osmium merge data/geofabrik/*.osm.pbf -o data/merged.osm.pbf

pbf-geneva:
	@rm -f data/geneva-*.osm.pbf
	osmium extract -b 4.7,45.1,10.5,47.8 data/merged.osm.pbf -o data/geneva-greater-area-all.osm.pbf
	osmium tags-filter data/geneva-greater-area-all.osm.pbf -o data/geneva-greater-area-filtered.osm.pbf \
		n/amenity,n/healthcare,n/office,n/public_transport,n/shop,n/tourism,a/amenity,a/healthcare,a/office,a/public_transport,a/shop,a/tourism