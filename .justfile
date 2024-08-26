image := "admwscki/kicad-kbplacer-primary"
in_docker_install := "pip install -r dev-requirements.txt -q"
in_docker_test := "pytest --no-cov -o=\"log_cli=False\""

test tag:
  docker run --rm -v $(pwd):$(pwd) -w $(pwd) -it {{image}}:{{tag}} \
    /bin/bash -c "{{in_docker_install}} && {{in_docker_test}} --html=report-{{tag}}.html"

test-all:
  just test 8.0.4-jammy
  just test 8.0.4-focal
  just test 7.0.11-focal
  just test 7.0.11-mantic

refresh-version:
  hatch build --hooks-only

main-dialog:
  python -m via_patterns.dialog
