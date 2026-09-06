#!/bin/bash
# Compile the Apple Vision OCR binary. Requires Xcode (or Command Line Tools) with Swift.
set -e
cd "$(dirname "$0")"
mkdir -p bin
swiftc -O -swift-version 5 -o bin/ocrshot src/ocrshot.swift
echo "built: $(pwd)/bin/ocrshot"
