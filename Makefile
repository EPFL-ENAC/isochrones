.PHONY: help
help: ## Show available targets
	@echo "============================================================================="
	@echo "Make targets"
	@echo "============================================================================="
	@echo ""
	@echo "📋 Prerequisites:"
	@echo "  • make"
	@echo "  • uv (Python project management - for backend/docs)"
	@echo ""
	@echo "📦 Setup:"
	@echo "  make install-tools    Install all dependencies and git hooks"
	@echo "  make clean            Clean all build artifacts"
	@echo "✨ Code Formatting/Linting:"
	@echo "  make format           Format all code"
	@echo "  make lint             Run all linters"
	@echo "  make test             Run all tests"
	@echo ""
	@echo "🗺️  Data Preparation:"
	@echo "  make pbf              Download and prepare OSM PBF files"
	@echo "  make pbf-geneva       Extract Geneva area from merged PBF"
	@echo "  make pbf-download     Download OSM PBF files from Geofabrik"
	@echo "  make pbf-merge        Merge downloaded PBF files into one"
	@echo ""
	@echo "============================================================================="

install:
	uv venv
	uv pip install -e .

test:
	uv run pytest -s

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

install-tools:
	sudo apt install -y osmium-tool josm

pbf: pbf-download pbf-merge

pbf-download:
	@rm -rf .data/geofabrik
	@mkdir -p .data/geofabrik
	wget https://download.geofabrik.de/europe/switzerland-latest.osm.pbf -O .data/geofabrik/switzerland-latest.osm.pbf
	wget https://download.geofabrik.de/europe/france/rhone-alpes-latest.osm.pbf -O .data/geofabrik/rhone-alpes-latest.osm.pbf
	wget https://download.geofabrik.de/europe/france/franche-comte-latest.osm.pbf -O .data/geofabrik/franche-comte-latest.osm.pbf
	wget https://download.geofabrik.de/europe/france/alsace-latest.osm.pbf -O .data/geofabrik/alsace-latest.osm.pbf
	wget https://download.geofabrik.de/europe/france/bourgogne-latest.osm.pbf -O .data/geofabrik/bourgogne-latest.osm.pbf
	wget https://download.geofabrik.de/europe/italy/nord-ovest-latest.osm.pbf -O .data/geofabrik/italy-nord-ovest-latest.osm.pbf

pbf-merge:
	@rm -f .data/merged.osm.pbf
	osmium merge .data/geofabrik/*.osm.pbf -o .data/merged.osm.pbf

pbf-geneva:
	@rm -f .data/geneva-*.osm.pbf
	osmium extract -b 4.7,45.1,10.5,47.8 .data/merged.osm.pbf -o .data/geneva-greater-area-all.osm.pbf
	osmium tags-filter .data/geneva-greater-area-all.osm.pbf --overwrite -o isochrones/data/geneva-greater-area.osm.pbf \
		n/amenity,n/healthcare,n/office,n/shop,n/tourism,a/amenity,a/healthcare,a/office,a/shop,a/tourism \
		n/public_transport,n/highway=bus_stop,n/railway \
		a/public_transport \
		nwr/route=bus,tram,train,subway,trolleybus,light_rail,ferry,monorail \
		r/type=route_master \
		r/public_transport=stop_area
