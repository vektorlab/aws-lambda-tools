#!/usr/bin/env bash
set -e
# Create a Python package to deploy to AWS Lambda.

PACKAGE=$1
BUILD_DIR="./_build"
PACKAGE_SHA=$(git rev-parse HEAD)
PACKAGE_DIR="./package"
PACKAGE_PATH="$PACKAGE_DIR/$PACKAGE_SHA-$PACKAGE.zip"

if [ ! "$PACKAGE" ]; then
    echo "You need to specify a package name"
    exit 1
fi

if [ ! -d "$PACKAGE_DIR" ]; then
    mkdir -v "$PACKAGE_DIR"
fi

if [ -d "$BUILD_DIR" ]; then
    rm -Rv "$BUILD_DIR"
    mkdir -v "$BUILD_DIR"
fi

if [ -d "$PACKAGE" ]; then
    pushd "$PACKAGE"
    zip -r "../$PACKAGE_PATH" *
    popd
fi

if [ -f "$PACKAGE/requirements.txt" ]; then
    pip install -r "$PACKAGE/requirements.txt" -t "$BUILD_DIR"
    pushd "$BUILD_DIR"
    zip -r --grow "../$PACKAGE_PATH" *
fi

