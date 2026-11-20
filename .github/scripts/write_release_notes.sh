#!/usr/bin/env bash
# Print the notes for the release of a version: the commits since the previous release, and how to install it.
#
# Usage: write_release_notes.sh <version> [<commit>]
# The commit defaults to HEAD. The previous release is the latest v* tag before the commit.
set -euo pipefail

version=$1
commit=${2:-HEAD}
repository=${GITHUB_REPOSITORY:-timbrinded/watercolour}
previous=$(git describe --tags --abbrev=0 --match 'v*' "$commit^" 2>/dev/null || true)

echo "## Changes"
echo
if [ -n "$previous" ]; then
    git log --reverse --format='- %s' "$previous..$commit"
else
    git log --reverse --format='- %s' "$commit"
fi
echo
echo "## Install"
echo
echo '```bash'
echo "uv tool install git+https://github.com/$repository@v$version"
echo '```'
echo
echo "The wheel and source archive below are built from this tag."
if [ -n "$previous" ]; then
    echo
    echo "**Full changelog**: https://github.com/$repository/compare/$previous...v$version"
fi
