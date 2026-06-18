image := "admwscki/kicad-kbplacer-primary"
in_docker_install := "pip install --no-cache-dir hatch -q"
in_docker_test := "hatch run test:test tests/"

test tag:
  docker run --rm -v $(pwd):$(pwd) -w $(pwd) -it {{image}}:{{tag}} \
    /bin/bash -c "{{in_docker_install}} && {{in_docker_test}} --html=report-{{tag}}.html"

test-latest10:
  just test 10.0.0-noble

test-latest9:
  just test 9.0.8-jammy

test-latest8:
  just test 8.0.9-jammy
  just test 8.0.9-focal

test-all:
  just test 10.0.0-noble
  just test 9.0.8-jammy
  just test 8.0.9-jammy
  just test 8.0.9-focal
  just test 7.0.11-focal
  just test 7.0.11-mantic

refresh-version:
  hatch build --hooks-only

main-dialog:
  python -m via_patterns.dialog main

rotate-dialog:
  python -m via_patterns.dialog rotate
