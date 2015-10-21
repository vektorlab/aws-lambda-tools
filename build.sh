#!/usr/bin/env bash
# Create a Python package to deploy to AWS Lambda.

PACKAGE=$1
BUILD_DIR="./_build"

if [ ! "$PACKAGE" ]; then
    echo "You need to specify a package name"
    exit 1
fi

echo "Building $PACKAGE"

if [ -d "$BUILD_DIR" ]; then
    rm -Rv "$BUILD_DIR"
fi

if [ -f "$PACKAGE/requirements.txt" ]; then
    mkdir -v "$BUILD_DIR"
    pip install -r "$PACKAGE/requirements.txt" -t "$BUILD_DIR"
    pushd "$PACKAGE"
    zip -r "$PACKAGE.zip" *
    mv -v "$PACKAGE.zip" ..
    popd
fi

if [ -d "$BUILD_DIR" ]; then
    pushd "$BUILD_DIR"
    zip -r --grow "../$PACKAGE.zip" *
    popd
fi

if [ -f "$PACKAGE/package.json" ]; then
    pushd "$PACKAGE"
    npm install
    zip -r "$PACKAGE" *
    mv -v "$PACKAGE.zip" ..
    popd
fi
