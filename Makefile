PY ?= python3

.PHONY: help tetris test play snapshot clean

help:
	@echo "make tetris    - compile projects 09+12 to dist/Tetris.hack (+ dist/build/*.vm)"
	@echo "make test      - run the toolchain + emulator regression suite"
	@echo "make play      - build, then play Tetris in a pygame window (needs pygame)"
	@echo "make snapshot  - build, then render a headless PNG to dist/tetris.png"
	@echo "make clean     - remove the dist/ build directory"

tetris:
	$(PY) tools/build.py

test:
	$(PY) tests/test_toolchain.py

play: tetris
	$(PY) tools/play.py dist/build

snapshot: tetris
	$(PY) tools/play.py dist/build --snapshot dist/tetris.png --warmup 14000000 --key 132

clean:
	rm -rf dist
