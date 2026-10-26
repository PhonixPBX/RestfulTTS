#!/bin/sh
# Release helpers used by the container workflow (see docs/RELEASING.md).
#
#   scripts/release.sh check <tag>   fail unless <tag> is v<version> of pyproject.toml and
#                                    src/restfultts/__init__.py, with a CHANGELOG.md section
#   scripts/release.sh notes <tag>   print the CHANGELOG.md section of <tag>
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

# expect <tag> <file> <found> <expected>
expect() {
	[ "$3" = "$4" ] && return
	echo "$1: $2 has version '$3', expected '$4'" >&2
	rc=1
}

check() {
	want=${1#v}
	[ "v$want" = "$1" ] || { echo "tag $1 does not start with v" >&2; exit 1; }
	py=$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml)
	init=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/restfultts/__init__.py)
	rc=0
	expect "$1" pyproject.toml "$py" "$want"
	expect "$1" src/restfultts/__init__.py "$init" "$want"
	grep -q "^## \[$want\]" CHANGELOG.md || { echo "$1: no '## [$want]' section in CHANGELOG.md" >&2; rc=1; }
	return $rc
}

notes() {
	want=${1#v}
	awk -v v="$want" '
		/^## \[/ { if (found) exit; found = index($0, "## [" v "]") == 1; next }
		/^\[[^]]+\]: / { next }
		found
	' CHANGELOG.md
}

case ${1:-} in
check) check "${2:?tag}" ;;
notes) notes "${2:?tag}" ;;
*)
	echo "usage: $0 check|notes <tag>" >&2
	exit 2
	;;
esac
