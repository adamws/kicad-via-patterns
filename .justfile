image := "admwscki/kicad-kbplacer-primary"
in_docker_install := "python3 -m pip install --upgrade hatch"
in_docker_test := "hatch run test"

test tag:
  docker run --rm -v $(pwd):$(pwd) -w $(pwd) -it {{image}}:{{tag}} \
    /bin/bash -c "{{in_docker_install}} && {{in_docker_test}}"

test-all:
  just test 8.0.4-jammy

refresh-version:
  hatch build --hooks-only
